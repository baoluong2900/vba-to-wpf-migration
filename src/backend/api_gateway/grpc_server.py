import os
import sys
import logging
from concurrent import futures
import json
import time
from pathlib import Path
import grpc

# Add necessary paths to sys.path
GATEWAY_DIR = Path(__file__).resolve().parent
BACKEND_DIR = GATEWAY_DIR.parent
WORKSPACE_DIR = BACKEND_DIR.parent

sys.path.insert(0, str(GATEWAY_DIR))
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "workflow" / "layer1"))
sys.path.insert(0, str(BACKEND_DIR / "workflow" / "layer2"))
sys.path.insert(0, str(BACKEND_DIR / "workflow" / "layer2" / "runners"))
sys.path.insert(0, str(BACKEND_DIR / "workflow" / "layer3"))
sys.path.insert(0, str(BACKEND_DIR / "workflow" / "layer3" / "scripts"))
sys.path.insert(0, str(BACKEND_DIR / "workflow" / "layer4"))
sys.path.insert(0, str(BACKEND_DIR / "workflow"))

# Load dotenv if present
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=GATEWAY_DIR / ".env")
    load_dotenv(dotenv_path=BACKEND_DIR / ".env")
except ImportError:
    pass

import workflow_pb2
import workflow_pb2_grpc

# --- Imports from Layers ---
from db.layer1_repo import Layer1Repo
from agents.bd_agent.bd_service import BDService
from agents.dd_agent.dd_service import DDService
from utils.cost_tracker import get_tracker, CostTracker

# For Layer 3
import layer3.server as l3_server

# For Layer 4
import layer4.sql_migration.router as l4_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vba_brain.grpc_gateway")

CONFIG_FILE = WORKSPACE_DIR.parent / "config.json"

# --- Cost Tracker Helpers ---
def _reset_tracker() -> CostTracker:
    from llm import cost_tracker as _ct
    _ct._tracker = CostTracker()
    return _ct._tracker

def _tracker_summary_dict(tracker: CostTracker, flow_type: str = "Unknown") -> dict:
    return {
        "flow_type": flow_type,
        "total_input_tokens": tracker.total_input_tokens,
        "total_output_tokens": tracker.total_output_tokens,
        "total_tokens": tracker.total_tokens,
        "total_cost_usd": round(tracker.total_cost, 6),
        "model_id": tracker.last_model_id,
        "records": [
            {
                "item": r.item_name,
                "model": r.model_id,
                "stage": r.stage,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": round(r.cost_usd, 6),
                "flow_type": r.flow_type,
            }
            for r in tracker.records
        ],
        "is_cached": tracker.total_tokens == 0 and len(tracker.records) == 0,
        "note": "Tokens=0 co thể do kết quả được tải từ Cache (đã chạy trước đó)." if tracker.total_tokens == 0 else ""
    }

def _resolve_stage(model: str) -> str:
    from config import STAGE
    if not model:
        return STAGE
    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        for pname, pcfg in cfg.get("llm_providers", {}).items():
            if model in pcfg.get("models", []):
                return "pilot" if pname == "beeknoee" else "dev"
    except Exception:
        pass
    return STAGE


# --- Service Implementations ---

class Layer1ServiceServicer(workflow_pb2_grpc.Layer1ServiceServicer):
    def __init__(self):
        self.repo = Layer1Repo()

    def ListForms(self, request, context):
        try:
            forms = self.repo.list_forms()
            return workflow_pb2.ListResponse(success=True, result=forms)
        except Exception as e:
            logger.error("ListForms error: %s", e)
            return workflow_pb2.ListResponse(success=False, error=str(e))

    def ListQueries(self, request, context):
        try:
            queries = self.repo.list_queries()
            return workflow_pb2.ListResponse(success=True, result=queries)
        except Exception as e:
            logger.error("ListQueries error: %s", e)
            return workflow_pb2.ListResponse(success=False, error=str(e))

    def ListAllItems(self, request, context):
        try:
            items = self.repo.list_all_items()
            return workflow_pb2.ListResponse(success=True, result=[json.dumps(item) for item in items])
        except Exception as e:
            logger.error("ListAllItems error: %s", e)
            return workflow_pb2.ListResponse(success=False, error=str(e))

    def GetDbQuery(self, request, context):
        try:
            screen_name = request.screen_name
            item_type = request.item_type.lower()
            deep = request.deep

            if deep:
                data = self.repo.get_dd_code_json_unified(screen_name)
            elif item_type == "auto" or not item_type:
                data = self.repo.get_bd_code_json_unified(screen_name)
            elif item_type == "form":
                data = self.repo.get_bd_code_json_form(screen_name)
            elif item_type == "report":
                data = self.repo.get_bd_code_json_report(screen_name)
            elif item_type == "module":
                data = self.repo.get_bd_code_json_module(screen_name)
            elif item_type == "query":
                data = self.repo.get_bd_code_json_query(screen_name)
            elif item_type == "macro":
                data = self.repo.get_bd_code_json_macro(screen_name)
            else:
                data = self.repo.get_bd_code_json_unified(screen_name)

            if not data:
                return workflow_pb2.DbQueryResponse(
                    success=False,
                    error=f"Document not found for '{screen_name}'"
                )

            return workflow_pb2.DbQueryResponse(
                success=True,
                result_json=json.dumps(data, ensure_ascii=False)
            )
        except Exception as e:
            logger.error("GetDbQuery error: %s", e)
            return workflow_pb2.DbQueryResponse(success=False, error=str(e))


class Layer2ServiceServicer(workflow_pb2_grpc.Layer2ServiceServicer):
    def __init__(self):
        self.repo = Layer1Repo()

    def GetConfig(self, request, context):
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            providers = cfg.get("llm_providers", {})
            models = []
            for pname, pcfg in providers.items():
                for m in pcfg.get("models", []):
                    models.append({"id": m, "label": m, "provider": pname})
            return workflow_pb2.ConfigResponse(success=True, models_json=json.dumps(models))
        except Exception as e:
            logger.error("GetConfig error: %s", e)
            return workflow_pb2.ConfigResponse(success=False, error=str(e))

    def GetModelsHealth(self, request, context):
        try:
            import concurrent.futures
            from config import AVAILABLE_MODELS
            from utils.llm_client import LLMClient

            client = LLMClient()

            def _test_model(model_id: str) -> dict:
                cfg = AVAILABLE_MODELS.get(model_id)
                if not cfg:
                    return {"model": model_id, "status": "unknown", "error": "Not in AVAILABLE_MODELS"}
                try:
                    result = client.chat(cfg, system="You are a test assistant.", user="Reply with just the word OK.")
                    if result and result.strip():
                        return {"model": model_id, "status": "ok"}
                    return {"model": model_id, "status": "error", "error": "Empty response"}
                except Exception as e:
                    err = str(e).lower()
                    if any(x in err for x in ["429", "quota", "rate limit", "insufficient_quota", "402"]):
                        return {"model": model_id, "status": "quota_exceeded", "error": str(e)[:120]}
                    return {"model": model_id, "status": "error", "error": str(e)[:120]}

            cfg_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            all_model_ids = []
            for pcfg in cfg_data.get("llm_providers", {}).values():
                all_model_ids.extend(pcfg.get("models", []))

            results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                f_map = {executor.submit(_test_model, m): m for m in all_model_ids}
                for f in concurrent.futures.as_completed(f_map, timeout=30):
                    r = f.result()
                    results[r["model"]] = {"status": r["status"], "error": r.get("error", "")}

            return workflow_pb2.ModelsHealthResponse(success=True, results_json=json.dumps(results))
        except Exception as e:
            logger.error("GetModelsHealth error: %s", e)
            return workflow_pb2.ModelsHealthResponse(success=False, error=str(e))

    def GetBdStatus(self, request, context):
        try:
            output_base = BACKEND_DIR / "layer2" / "output"
            s4_file = output_base / "bd_flow" / "s4_bd_final" / f"{request.screen_name}.json"

            d4_file = None
            for cat in ("screen", "common", "macro"):
                candidate = output_base / "dd_flow" / cat / "d4_dd_final" / f"{request.screen_name}.json"
                if candidate.exists():
                    d4_file = candidate
                    break

            return workflow_pb2.BdStatusResponse(
                success=True,
                screen_name=request.screen_name,
                bd_done=s4_file.exists(),
                dd_done=d4_file is not None,
                s4_path=str(s4_file) if s4_file.exists() else "",
                d4_path=str(d4_file) if d4_file else ""
            )
        except Exception as e:
            logger.error("GetBdStatus error: %s", e)
            return workflow_pb2.BdStatusResponse(success=False, error=str(e))

    def RunBdFlowFull(self, request, context):
        try:
            db_data = json.loads(request.db_data_json) if request.db_data_json else {}
            model = request.model if request.model else None
            
            # Auto-fetch if data is empty
            _form_vba = (db_data.get("form") or {}).get("vba_procedures", [])
            _mod_procs = (db_data.get("module") or {}).get("procedures", [])
            _is_thin = not _form_vba and not _mod_procs and not db_data.get("macro")

            if _is_thin:
                try:
                    db_data = self.repo.get_bd_code_json_unified(request.screen_name)
                except Exception:
                    pass

            if "form" in db_data:
                item_type = "form"
            elif "report" in db_data:
                item_type = "report"
            elif "module" in db_data:
                item_type = "module"
            else:
                item_type = "form"

            stage = _resolve_stage(model)
            service = BDService(stage=stage)
            tracker = _reset_tracker()
            
            result_dict = service.run_full_flow(
                screen_name=request.screen_name,
                bd_code_json=db_data,
                item_type=item_type,
                repo=self.repo,
                model_id=model,
                force=request.force
            )

            # Auto push to mongo
            try:
                import push_to_mongo
                push_to_mongo.push_bd_one(request.screen_name)
            except Exception as _pe:
                logger.warning("[BD Flow] MongoDB push failed for '%s': %s", request.screen_name, _pe)

            excel_path = tracker.save_excel_report(label=request.screen_name, flow_type="BD Agent")
            json_path = tracker.save_report(label=request.screen_name, flow_type="BD Agent")

            return workflow_pb2.BdAgentResponse(
                success=True,
                result_json=json.dumps(result_dict, ensure_ascii=False),
                paths_json=json.dumps(result_dict),
                token_stats_json=json.dumps(_tracker_summary_dict(tracker, "BD Agent")),
                log_files_json=json.dumps({"excel": excel_path, "json": json_path})
            )
        except Exception as e:
            logger.error("RunBdFlowFull error: %s", e)
            return workflow_pb2.BdAgentResponse(success=False, error=str(e))

    def RunBdFlowExtract(self, request, context):
        try:
            db_data = json.loads(request.db_data_json) if request.db_data_json else {}
            _thin = not (db_data.get("form") or {}).get("vba_procedures") and not db_data.get("macro")
            if _thin:
                try:
                    db_data = self.repo.get_bd_code_json_unified(request.screen_name)
                except Exception:
                    pass

            service = BDService()
            res = service.run_extract_phase(
                screen_name=request.screen_name,
                bd_code_json=db_data,
                repo=self.repo
            )
            return workflow_pb2.BdAgentResponse(
                success=True,
                result_json=json.dumps(res, ensure_ascii=False),
                paths_json=json.dumps(res)
            )
        except Exception as e:
            logger.error("RunBdFlowExtract error: %s", e)
            return workflow_pb2.BdAgentResponse(success=False, error=str(e))

    def RunBdFlowAnalysis(self, request, context):
        try:
            db_data = json.loads(request.db_data_json) if request.db_data_json else {}
            model = request.model if request.model else None
            _thin = not (db_data.get("form") or {}).get("vba_procedures") and not db_data.get("macro")
            if _thin:
                try:
                    db_data = self.repo.get_bd_code_json_unified(request.screen_name)
                except Exception:
                    pass

            stage = _resolve_stage(model)
            service = BDService(stage=stage)
            
            extract_res = service.run_extract_phase(
                screen_name=request.screen_name,
                bd_code_json=db_data,
                repo=self.repo
            )
            
            tracker = _reset_tracker()
            res = service.run_analysis_phase(
                screen_name=request.screen_name,
                bd_code_json=db_data,
                mapped_data=extract_res["mapped_data"],
                repo=self.repo,
                model_id=model,
                force=request.force
            )

            excel_path = tracker.save_excel_report(label=request.screen_name, flow_type="BD Agent")
            json_path = tracker.save_report(label=request.screen_name, flow_type="BD Agent")

            return workflow_pb2.BdAgentResponse(
                success=True,
                result_json=json.dumps(res, ensure_ascii=False),
                paths_json=json.dumps(res),
                token_stats_json=json.dumps(_tracker_summary_dict(tracker, "BD Agent")),
                log_files_json=json.dumps({"excel": excel_path, "json": json_path})
            )
        except Exception as e:
            logger.error("RunBdFlowAnalysis error: %s", e)
            return workflow_pb2.BdAgentResponse(success=False, error=str(e))

    def RunDdFlowFull(self, request, context):
        try:
            stage = _resolve_stage(request.model)
            service = DDService()
            tracker = _reset_tracker()
            result_dict = service.run_full_flow(
                screen_name=request.screen_name,
                model_id=request.model or None,
                force=request.force,
            )

            try:
                import push_to_mongo
                push_to_mongo.push_dd_one(request.screen_name)
            except Exception as _pe:
                logger.warning("[DD Flow] MongoDB push failed for '%s': %s", request.screen_name, _pe)

            excel_path = tracker.save_excel_report(label=request.screen_name, flow_type="DD Agent")
            json_path = tracker.save_report(label=request.screen_name, flow_type="DD Agent")

            return workflow_pb2.DdFlowResponse(
                success=True,
                result_json=json.dumps(result_dict, ensure_ascii=False),
                paths_json=json.dumps(result_dict),
                token_stats_json=json.dumps(_tracker_summary_dict(tracker, "DD Agent")),
                log_files_json=json.dumps({"excel": excel_path, "json": json_path})
            )
        except Exception as e:
            logger.error("RunDdFlowFull error: %s", e)
            return workflow_pb2.DdFlowResponse(success=False, error=str(e))

    def GetTokenReport(self, request, context):
        try:
            tracker = get_tracker()
            summary = _tracker_summary_dict(tracker)
            return workflow_pb2.TokenReportResponse(success=True, token_stats_json=json.dumps(summary))
        except Exception as e:
            logger.error("GetTokenReport error: %s", e)
            return workflow_pb2.TokenReportResponse(success=False, error=str(e))


class Layer3ServiceServicer(workflow_pb2_grpc.Layer3ServiceServicer):
    def ListItems(self, request, context):
        try:
            res = l3_server.list_items()
            if isinstance(res, dict) and res.get("success"):
                return workflow_pb2.ListResponse(success=True, result=[json.dumps(item) for item in res.get("result", [])])
            return workflow_pb2.ListResponse(success=False, error=str(res))
        except Exception as e:
            logger.error("ListItems error: %s", e)
            return workflow_pb2.ListResponse(success=False, error=str(e))

    def ListOutputs(self, request, context):
        try:
            res = l3_server.list_outputs()
            if isinstance(res, dict) and res.get("success"):
                return workflow_pb2.ListResponse(success=True, result=[json.dumps(f) for f in res.get("files", [])])
            return workflow_pb2.ListResponse(success=False, error=str(res))
        except Exception as e:
            logger.error("ListOutputs error: %s", e)
            return workflow_pb2.ListResponse(success=False, error=str(e))

    def GenBd(self, request, context):
        try:
            class GenReqObj:
                screenName = request.screen_name
                type = request.type
            
            res = l3_server.gen_bd(GenReqObj())
            return workflow_pb2.GenResponse(success=True, result_json=json.dumps(res))
        except Exception as e:
            logger.error("GenBd error: %s", e)
            return workflow_pb2.GenResponse(success=False, error=str(e))

    def GenDd(self, request, context):
        try:
            class GenReqObj:
                screenName = request.screen_name
                type = request.type
            
            res = l3_server.gen_dd(GenReqObj())
            return workflow_pb2.GenResponse(success=True, result_json=json.dumps(res))
        except Exception as e:
            logger.error("GenDd error: %s", e)
            return workflow_pb2.GenResponse(success=False, error=str(e))

    def GenAll(self, request, context):
        try:
            class GenReqObj:
                screenName = request.screen_name
                type = request.type
            
            res = l3_server.gen_all(GenReqObj())
            return workflow_pb2.GenResponse(success=True, result_json=json.dumps(res))
        except Exception as e:
            logger.error("GenAll error: %s", e)
            return workflow_pb2.GenResponse(success=False, error=str(e))

    def DownloadExcel(self, request, context):
        try:
            res = l3_server.download_file(request.doc_kind, request.doc_type, request.filename)
            # res is a FileResponse. Let's read the file contents as bytes
            file_path = Path(res.path)
            if file_path.exists():
                content = file_path.read_bytes()
                return workflow_pb2.DownloadResponse(success=True, file_content=content, content_type=res.media_type)
            return workflow_pb2.DownloadResponse(success=False, error="File path does not exist")
        except Exception as e:
            logger.error("DownloadExcel error: %s", e)
            return workflow_pb2.DownloadResponse(success=False, error=str(e))


class Layer4ServiceServicer(workflow_pb2_grpc.Layer4ServiceServicer):
    def ListMigrationQueries(self, request, context):
        try:
            res = l4_router.list_queries()
            if isinstance(res, dict) and res.get("success"):
                return workflow_pb2.MigrationQueriesResponse(success=True, queries_json=json.dumps(res.get("result", [])))
            return workflow_pb2.MigrationQueriesResponse(success=False, error=str(res))
        except Exception as e:
            logger.error("ListMigrationQueries error: %s", e)
            return workflow_pb2.MigrationQueriesResponse(success=False, error=str(e))

    def GetMigrationQuery(self, request, context):
        try:
            res = l4_router.get_query(request.name)
            if isinstance(res, dict) and res.get("success"):
                return workflow_pb2.MigrationQueryDetailResponse(success=True, query_json=json.dumps(res.get("result", {})))
            return workflow_pb2.MigrationQueryDetailResponse(success=False, error=str(res))
        except Exception as e:
            logger.error("GetMigrationQuery error: %s", e)
            return workflow_pb2.MigrationQueryDetailResponse(success=False, error=str(e))

    def UpdateMigrationQuery(self, request, context):
        try:
            class SaveReqObj:
                target_sql = request.target_sql
                target_query = json.loads(request.target_query_json) if request.target_query_json else {}
                notes = request.notes
                status = request.status
                reviewer = request.reviewer
                description = request.description
                model = request.model
            
            res = l4_router.update_query(request.name, SaveReqObj())
            if isinstance(res, dict) and res.get("success"):
                # Fetch updated query
                updated = l4_router.get_query(request.name)
                return workflow_pb2.MigrationQueryDetailResponse(success=True, query_json=json.dumps(updated.get("result", {})))
            return workflow_pb2.MigrationQueryDetailResponse(success=False, error=str(res))
        except Exception as e:
            logger.error("UpdateMigrationQuery error: %s", e)
            return workflow_pb2.MigrationQueryDetailResponse(success=False, error=str(e))

    def ConvertQuery(self, request, context):
        try:
            class ConvertReqObj:
                name = request.name
                model = request.model
            
            res = l4_router.convert_query(ConvertReqObj())
            if isinstance(res, dict) and res.get("success"):
                # Fetch updated query
                updated = l4_router.get_query(request.name)
                return workflow_pb2.MigrationQueryDetailResponse(success=True, query_json=json.dumps(updated.get("result", {})))
            return workflow_pb2.MigrationQueryDetailResponse(success=False, error=str(res))
        except Exception as e:
            logger.error("ConvertQuery error: %s", e)
            return workflow_pb2.MigrationQueryDetailResponse(success=False, error=str(e))

    def SeedQueries(self, request, context):
        try:
            # Replicate route seed_queries logic if it exists
            # In router.py, there is a seed endpoint. Let's see if we can trigger it.
            # Usually, seed uses l4_router.seed_queries() or similar. Let's try calling it if defined.
            if hasattr(l4_router, 'seed_queries'):
                res = l4_router.seed_queries()
                return workflow_pb2.SeedQueriesResponse(success=True, count=res.get("count", 0))
            else:
                # Fallback to manual seeding
                from layer4.sql_migration.seed_queries_v2 import seed_v2
                count = seed_v2()
                return workflow_pb2.SeedQueriesResponse(success=True, count=count)
        except Exception as e:
            logger.error("SeedQueries error: %s", e)
            return workflow_pb2.SeedQueriesResponse(success=False, error=str(e))

    def GetStats(self, request, context):
        try:
            res = l4_router.get_stats()
            return workflow_pb2.StatsResponse(success=True, stats_json=json.dumps(res))
        except Exception as e:
            logger.error("GetStats error: %s", e)
            return workflow_pb2.StatsResponse(success=False, error=str(e))


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    workflow_pb2_grpc.add_Layer1ServiceServicer_to_server(Layer1ServiceServicer(), server)
    workflow_pb2_grpc.add_Layer2ServiceServicer_to_server(Layer2ServiceServicer(), server)
    workflow_pb2_grpc.add_Layer3ServiceServicer_to_server(Layer3ServiceServicer(), server)
    workflow_pb2_grpc.add_Layer4ServiceServicer_to_server(Layer4ServiceServicer(), server)
    server.add_insecure_port('[::]:50051')
    logger.info("Starting Unified gRPC API Gateway on port 50051...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
