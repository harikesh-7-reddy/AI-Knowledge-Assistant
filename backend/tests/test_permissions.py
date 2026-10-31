from app.database import visible_document_sql


def test_admin_can_see_all_documents():
    clause, params = visible_document_sql({"role": "admin", "department": "IT", "id": 1})
    assert clause == "1=1"
    assert params == ()


def test_employee_visibility_is_department_scoped():
    clause, params = visible_document_sql({"role": "employee", "department": "HR", "id": 7})
    assert "d.access_level = 'public'" in clause
    assert "d.department = ?" in clause
    assert "d.owner_id = ?" in clause
    assert params == ("HR", 7)
