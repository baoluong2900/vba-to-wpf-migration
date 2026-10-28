"""agents/repo/tool_repo.merge_csharp_code — re-runs must never lose the type declaration or members."""
from __future__ import annotations

from agents.repo import tool_repo as tr


def _method(name: str, query: str, sql: str = "SELECT 1") -> dict:
    return {
        "name": name,
        "return_type": "IEnumerable<XEntity>",
        "params": "",
        "dapper_params": "",
        "base_sql": sql,
        "deps": [],
        "comment": f"    /// <summary>\n    /// {query}\n    /// </summary>\n    /// <returns></returns>\n",
        "is_action": False,
        "stub_reason": "",
    }


def _repo(base: str, table: str, *methods: dict) -> str:
    return tr.gen_repository(base, f"{base}Entity", list(methods), {}, namespace_suffix=base, jp_table_name=table)


def _iface(base: str, table: str, *methods: dict) -> str:
    return tr.gen_interface(base, list(methods), namespace_suffix=base, jp_table_name=table)


def test_rerun_keeps_class_when_table_summary_equals_query_name():
    # Empty FROM makes the query its own table: class and method share the same <summary> text
    code = _repo("Q000TLoginUser", "Q000_T_LoginUser", _method("GetUserInfoAsync", "Q000_T_LoginUser"))
    merged = tr.merge_csharp_code(code, code)
    assert "public class Q000TLoginUserRepository : IQ000TLoginUserRepository" in merged
    assert "private readonly DapperContext _context;" in merged
    assert merged.count("public async Task<IEnumerable<XEntity>> GetUserInfoAsync(") == 1


def test_rerun_keeps_interface_when_table_summary_equals_query_name():
    code = _iface("Access配信日", "Access配信日", _method("GetCommentAsync", "Access配信日"))
    merged = tr.merge_csharp_code(code, code)
    assert "public interface IAccess配信日Repository" in merged
    assert merged.count("GetCommentAsync(") == 1


def test_japanese_class_names_merge_members_from_both_forms():
    first = _repo("T023地区CD設定", "T023_地区CD設定", _method("SetAreaCdAsync", "Q_A"))
    second = _repo("T023地区CD設定", "T023_地区CD設定", _method("GetAreaAsync", "Q_B"))
    merged = tr.merge_csharp_code(first, second)
    assert "public class T023地区CD設定Repository : IT023地区CD設定Repository" in merged
    assert "SetAreaCdAsync(" in merged and "GetAreaAsync(" in merged

    iface = tr.merge_csharp_code(_iface("T023地区CD設定", "T", _method("SetAreaCdAsync", "Q_A")),
                                 _iface("T023地区CD設定", "T", _method("GetAreaAsync", "Q_B")))
    assert "SetAreaCdAsync(" in iface and "GetAreaAsync(" in iface


def test_member_with_same_query_name_is_replaced_in_place():
    old = _repo("Auth", "T101_ID_PASS", _method("IdPassAsync", "T_ID_Pass", "SELECT old_col"), _method("OtherAsync", "Q_Other"))
    new = _repo("Auth", "T101_ID_PASS", _method("IdPassAsync", "T_ID_Pass", "SELECT new_col"))
    merged = tr.merge_csharp_code(old, new)
    assert "new_col" in merged and "old_col" not in merged
    assert merged.count("IdPassAsync(") == 1
    assert "OtherAsync(" in merged


def test_headerless_file_is_rebuilt_around_the_generated_type():
    corrupted = (
        "using System.Text;\n\nnamespace vba_brain.Infrastructure.Persistence.Repositories;\n\n"
        "    /// <summary>\n    /// Q_Old\n    /// </summary>\n"
        "    public async Task<IEnumerable<XEntity>> OldAsync()\n    {\n        return null;\n    }\n"
    )
    new = _repo("Q000TLoginUser", "Q000_T_LoginUser", _method("GetUserInfoAsync", "Q000_T_LoginUser"))
    merged = tr.merge_csharp_code(corrupted, new)
    assert "public class Q000TLoginUserRepository" in merged
    assert "OldAsync(" in merged and "GetUserInfoAsync(" in merged
    assert merged.rstrip().endswith("}")


def test_property_replacement_with_backslashes_does_not_break_regex():
    entity = "using X;\n\nnamespace N;\n\npublic class AEntity : BaseEntity\n{\n    [Column(\"列\")]\n    public string Old { get; set; } = string.Empty;\n}\n"
    new = "using X;\n\nnamespace N;\n\npublic class AEntity : BaseEntity\n{\n    [Column(\"列\")]\n    public string New { get; set; } = string.Empty;  // C:\\Users\\x\n}\n"
    merged = tr.merge_csharp_code(entity, new)
    assert "public string New" in merged and "C:\\Users\\x" in merged
    assert "public string Old" not in merged
