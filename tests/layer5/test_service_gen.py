"""agents/service — plan-based service generation (names, repo-contract arguments, auth, namespaces)."""
from __future__ import annotations

import re

import pytest

from agents.service import agent_service
from agents.service import tool_service_gen as ts


def _contract(*repos: dict, dtos: list[dict] | None = None) -> dict:
    return {"repositories": list(repos), "dtos": dtos or [], "entities": []}


def _service_input(form_name: str, events: list[dict], contracts: dict) -> dict:
    return {"form_name": form_name, "events": events, "repository_contracts": contracts}


ORDER_REPO = {
    "repository_name": "TOrderRepository", "interface_name": "ITOrderRepository", "table_name": "T_Order",
    "function": [{
        "function_name": "GetOrderAsync", "query_name": "Q_Order", "sheet_query_name": "F000_SelQuery01",
        "input": [{"name": "orderNo", "type": "int", "description": "注文番号", "vba": "txt注文番号"},
                  {"name": "since", "type": "DateTime?", "description": "日付", "vba": "txt日付"}],
        "output": [{"name": "TOrderEntity", "type": "entity", "namespace": "vba_brain.Domain.Entities"}],
        "return_type": "IEnumerable<TOrderEntity>", "implemented": True,
    }],
}


@pytest.mark.parametrize("trigger", ["画面を開く時", "On Open", "onopen", "on_open"])
def test_trigger_vocabularies_share_one_key(trigger):
    assert ts.trigger_key(trigger) == "onopen"
    assert ts.vba_handler_suffix(trigger) == "_Open"


def test_english_triggers_map_to_method_names_and_vba_suffixes():
    assert ts.derive_method_name({"event_trigger": "After Update", "module_id": "F003"}, "X") == "SubmitAsync"
    assert ts.derive_method_name({"event_trigger": "On Double Click", "module_id": "F009"}, "X") == "OnDoubleClickAsync"
    assert ts.vba_handler_suffix("On Key Down") == "_KeyDown"
    assert ts.vba_handler_suffix("Before Update") == "_BeforeUpdate"


def test_method_names_and_class_tokens_are_unique():
    events = [{"module_id": "受注", "event_trigger": "On Click"}, {"module_id": "受注2", "event_trigger": "On Click"},
              {"module_id": "F001", "event_trigger": "On Click"}]
    names = ts.assign_method_names(events, "Order")
    assert len(set(names)) == 3 and names[0] == "OnClickAsync"
    assert ts.assign_class_tokens(events, "Order") == ["Order", "Order2", "F001"]


def test_call_arguments_follow_the_repository_input_contract():
    event = {"module_id": "F000", "event_trigger": "On Open", "query_mappings": [
        {"logic_query_name": "Q_Order", "sheet_name": "F000_SelQuery01",
         "parameters": [{"name": "txt日付", "io": "I", "mapping": "＜パラメータ＞.txt日付"},
                        {"name": "txt注文番号", "io": "I", "mapping": "＜パラメータ＞.txt注文番号"},
                        {"name": "Requery", "io": "I", "mapping": "＜パラメータ＞.Requery"}]}]}
    si = _service_input("F_Order", [event], _contract(ORDER_REPO))
    impl = ts.generate_service_impl(si)
    req, res = ts.generate_service_dtos(si)
    # repo order and types, not the DD parameter order
    assert "await _tOrderRepository.GetOrderAsync(request.OrderNo, request.Since);" in impl
    assert "public int OrderNo { get; set; }" in req and "public DateTime? Since { get; set; }" in req
    assert "Requery" not in req
    assert "public IEnumerable<TOrderEntity>? Data { get; set; }" in res and "using vba_brain.Domain.Entities;" in res
    plan = ts.build_service_plan(si)
    assert plan["events"][0]["request_props"][0]["control"] == "txt注文番号"


def test_dto_input_becomes_an_object_initializer():
    repo = {"repository_name": "TOrderRepository", "table_name": "T_Order", "function": [{
        "function_name": "SearchAsync", "query_name": "Q_Search", "sheet_query_name": "F001_SelQuery01",
        "input": [{"name": "SearchInputDto", "type": "dto", "namespace": "vba_brain.Domain.DTOs.TOrder"}],
        "output": [{"name": "SearchDto", "type": "dto", "namespace": "vba_brain.Domain.DTOs.TOrder"}],
        "return_type": "IEnumerable<SearchDto>"}]}
    dto = {"dto_name": "SearchInputDto", "namespace": "vba_brain.Domain.DTOs.TOrder",
           "fields": [{"name": "A", "type": "string"}, {"name": "B", "type": "int"},
                      {"name": "C", "type": "string"}, {"name": "D", "type": "bool"}]}
    event = {"module_id": "F001", "event_trigger": "On Click",
             "query_mappings": [{"logic_query_name": "Q_Search", "sheet_name": "F001_SelQuery01"}]}
    si = _service_input("F_Order", [event], _contract(repo, dtos=[dto]))
    impl = ts.generate_service_impl(si)
    req, res = ts.generate_service_dtos(si)
    assert ("SearchAsync(new vba_brain.Domain.DTOs.TOrder.SearchInputDto "
            "{ A = request.A, B = request.B, C = request.C, D = request.D });") in impl
    assert "public int B { get; set; }" in req and "public bool D { get; set; }" in req
    assert "IEnumerable<vba_brain.Domain.DTOs.TOrder.SearchDto>? Data" in res


AUTH_REPO = {
    "repository_name": "TIDPassRepository", "table_name": "T_ID_Pass", "function": [
        {"function_name": "IdPassAsync", "query_name": "T_ID_Pass", "sheet_query_name": "F003_SelQuery01",
         "input": [], "output": [{"name": "TIDPassEntity", "type": "entity"}],
         "return_type": "IEnumerable<TIDPassEntity>"},
        {"function_name": "VerifyCredentialsAsync", "kind": "credential_check", "query_name": "",
         "input": [{"name": "id", "type": "string", "description": "ユーザーID"},
                   {"name": "password", "type": "string", "description": "パスワード"}],
         "output": [{"name": "", "type": "bool"}], "return_type": "bool"},
    ]}


def test_auth_event_uses_the_parameterized_credential_check():
    event = {"module_id": "F003", "event_trigger": "After Update", "event_content": "ユーザーIDとパスワードを検証する",
             "query_mappings": [{"logic_query_name": "T_ID_Pass", "sheet_name": "F003_SelQuery01"}]}
    si = _service_input("F_Login", [event], _contract(AUTH_REPO))
    impl = ts.generate_service_impl(si)
    req, res = ts.generate_service_dtos(si)
    assert "await _tIDPassRepository.VerifyCredentialsAsync(request.Id, request.Password);" in impl
    assert "IdPassAsync" not in impl and "AuthEntity" not in impl
    assert "Authenticated = verifyCredentials," in impl
    assert "public bool Authenticated { get; set; }" in res and "TIDPassEntity" not in res
    assert "public string Password { get; set; }" in req


def test_bare_id_wording_is_not_an_auth_event():
    assert not ts.is_auth_event({"event_content": "ユーザーIDを表示する", "steps": [{"detail": "ID一覧"}]})
    assert ts.is_auth_event({"steps": [{"detail": "パスワードを照合"}]})


def test_every_assigned_response_property_is_declared():
    events = [
        {"module_id": "F000", "event_trigger": "On Open",
         "query_mappings": [{"logic_query_name": "Q_Order"}, {"logic_query_name": "Q_Count"}]},
    ]
    count_repo = {"repository_name": "CountRepository", "table_name": "T", "function": [{
        "function_name": "GetCountAsync", "query_name": "Q_Count", "input": [],
        "output": [{"name": "", "type": "int"}], "return_type": "IEnumerable<int>"}]}
    si = _service_input("F_Order", events, _contract(ORDER_REPO, count_repo))
    plan = ts.build_service_plan(si)
    declared = {p["name"] for p in plan["events"][0]["response_props"]}
    assigned = set(re.findall(r"^\s+(\w+) = ", plan["events"][0]["method_code"], re.M)) - {"var"}
    assert assigned <= declared
    assert "Count = count?.FirstOrDefault()," in plan["events"][0]["method_code"]


def test_dto_namespaces_use_the_shared_sanitizer():
    si = _service_input("F000_Splash(M)", [{"module_id": "F000", "event_trigger": "On Open"}], _contract())
    req, res = ts.generate_service_dtos(si)
    impl = ts.generate_service_impl(si)
    assert "namespace vba_brain.Application.DTOs.Requests.F000_Splash_M" in req
    assert "namespace vba_brain.Application.DTOs.Responses.F000_Splash_M" in res
    assert "using vba_brain.Application.DTOs.Requests.F000_Splash_M;" in impl
    declarations = [ln for ln in (req + res + impl).splitlines() if ln.strip().startswith(("namespace ", "using "))]
    assert not any("(" in ln for ln in declarations)


def test_me_enrichment_only_adds_input_controls_and_keeps_dd_untouched():
    dd = {"sheet_2_overview": {"parameter_info": [{"item_name": "顧客", "data_type": "Text Box"}]},
          "sheet_3_detail_specs": [{"module_id": "F000", "module_name": "-", "event_trigger": "On Open",
                                    "query_mappings": [{"logic_query_name": "Q", "parameters": []}]}]}
    functions = [{"handler": "Form_Open", "code": "x = DLookup(\"a\", \"b\")\nMe.txtID\nMe.Requery\nMe.顧客\nMe.lbl1"}]
    si = agent_service.build_service_input("F_X", dd, {}, functions, filter_mode="any_repo_signal")
    params = [p["name"] for p in si["events"][0]["query_mappings"][0]["parameters"]]
    assert params == ["txtID", "顧客"]
    assert dd["sheet_3_detail_specs"][0]["query_mappings"][0]["parameters"] == []


def test_contract_keys_follow_the_bd_module_id():
    registry = {"F004": {"vba_handler": "閉じる_Click", "event": "onclick", "control": "閉じる"}}
    assert agent_service.contract_method_key("F003", {"module_id": "F003"}, registry) == "F003"
    bd_event = {"module_id": "R005_作業依頼書", "notes": "閉じる_Click", "event_trigger": "On Click"}
    assert agent_service.contract_method_key("R005_作業依頼書", bd_event, registry) == "F004"
    assert agent_service.contract_method_key("R005_作業依頼書", None, registry) == "R005_作業依頼書"


def test_contract_vba_handler_prefers_bd_notes():
    assert agent_service.contract_vba_handler({"notes": "Form_Open"}, {}) == "Form_Open"
    event = {"matched_vba": {"handler": "txtID_AfterUpdate"}}
    assert agent_service.contract_vba_handler({"notes": "-"}, event) == "txtID_AfterUpdate"
    assert agent_service.contract_vba_handler({"notes": "[参照]"}, {}) == ""
