"""Comprehensive smoke test for Task and Category CRUD endpoints."""
import requests
import sys
import time

BASE = "http://localhost:8000/api/v1"
AUTH = f"{BASE}/auth"
passed = 0
failed = 0
TS = str(int(time.time()))  # unique suffix for idempotency


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label} — {detail}")


def main():
    global passed, failed

    # ---- Setup: register a fresh user & get token ----
    r = requests.post(f"{AUTH}/register/", json={
        "username": f"crud_{TS}",
        "email": f"crud_{TS}@example.com",
        "password": "CrudPass123!",
        "password_confirm": "CrudPass123!",
    })
    token = r.json()["tokens"]["access"]
    headers = {"Authorization": f"Bearer {token}"}

    # ---- Register a second user to test cross-user isolation ----
    r2 = requests.post(f"{AUTH}/register/", json={
        "username": f"other_{TS}",
        "email": f"other_{TS}@example.com",
        "password": "OtherPass123!",
        "password_confirm": "OtherPass123!",
    })
    other_token = r2.json()["tokens"]["access"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # ==================================================================
    print("\n=== CATEGORY CRUD ===")
    # ==================================================================

    # 1. Create category
    r = requests.post(f"{BASE}/categories/", json={"name": f"Work_{TS}", "colour": "#ef4444"}, headers=headers)
    check("Create category", r.status_code == 201, f"{r.status_code} {r.text}")
    cat_id = r.json()["id"]

    # 2. Create second category
    r = requests.post(f"{BASE}/categories/", json={"name": f"Personal_{TS}", "colour": "#3b82f6"}, headers=headers)
    check("Create second category", r.status_code == 201, f"{r.status_code}")
    cat2_id = r.json()["id"]

    # 3. List categories
    r = requests.get(f"{BASE}/categories/", headers=headers)
    check("List categories", r.status_code == 200 and len(r.json()["results"]) >= 2, f"{r.status_code}")

    # 4. Category has task_count
    check("Category has task_count", "task_count" in r.json()["results"][0])

    # 5. Update category
    updated_name = f"WorkUpd_{TS}"
    r = requests.patch(f"{BASE}/categories/{cat_id}/", json={"name": updated_name}, headers=headers)
    check("Update category", r.status_code == 200 and r.json()["name"] == updated_name, f"{r.status_code}")

    # 6. Duplicate category name validation
    r = requests.post(f"{BASE}/categories/", json={"name": f"Personal_{TS}"}, headers=headers)
    check("Duplicate name rejected", r.status_code == 400, f"{r.status_code} {r.text}")

    # 7. Invalid colour validation
    r = requests.post(f"{BASE}/categories/", json={"name": "Bad", "colour": "red"}, headers=headers)
    check("Invalid colour rejected", r.status_code == 400, f"{r.status_code}")

    # 8. Cross-user isolation — other user can't see our categories
    r = requests.get(f"{BASE}/categories/", headers=other_headers)
    our_ids = {cat_id, cat2_id}
    their_ids = {c["id"] for c in r.json()["results"]}
    check("Cross-user category isolation", len(our_ids & their_ids) == 0)

    # ==================================================================
    print("\n=== TASK CRUD ===")
    # ==================================================================

    # 9. Create task (minimal)
    r = requests.post(f"{BASE}/tasks/", json={"title": "Basic task"}, headers=headers)
    check("Create task (minimal)", r.status_code == 201, f"{r.status_code} {r.text}")
    task1_id = r.json()["id"]
    check("Default status=todo", r.json()["status"] == "todo")
    check("Default priority=medium", r.json()["priority"] == "medium")

    # 10. Create task with all fields
    r = requests.post(f"{BASE}/tasks/", json={
        "title": "Full task",
        "description": "A detailed description",
        "priority": "high",
        "due_date": "2026-12-31",
        "category": cat_id,
    }, headers=headers)
    check("Create task (full)", r.status_code == 201, f"{r.status_code} {r.text}")
    task2_id = r.json()["id"]
    check("Category assigned", r.json()["category"] == cat_id)
    check("category_name populated", r.json()["category_name"] == updated_name)
    check("is_overdue=false", r.json()["is_overdue"] is False)

    # 11. Create more tasks for filtering
    requests.post(f"{BASE}/tasks/", json={"title": "Urgent task", "priority": "urgent", "due_date": "2026-06-15"}, headers=headers)
    requests.post(f"{BASE}/tasks/", json={"title": "Done task", "status": "todo"}, headers=headers)
    # Immediately mark as done via the proper transition
    r_done = requests.post(f"{BASE}/tasks/", json={"title": "Completed task"}, headers=headers)
    done_id = r_done.json()["id"]
    requests.patch(f"{BASE}/tasks/{done_id}/", json={"status": "in_progress"}, headers=headers)
    requests.patch(f"{BASE}/tasks/{done_id}/", json={"status": "done"}, headers=headers)

    # 12. List tasks
    r = requests.get(f"{BASE}/tasks/", headers=headers)
    check("List tasks", r.status_code == 200, f"{r.status_code}")
    check("Pagination present", "results" in r.json() and "count" in r.json())
    total_count = r.json()["count"]
    check(f"Tasks created (count={total_count})", total_count >= 5)

    # 13. Get single task
    r = requests.get(f"{BASE}/tasks/{task2_id}/", headers=headers)
    check("Get single task", r.status_code == 200 and r.json()["title"] == "Full task")

    # 14. Update task
    r = requests.patch(f"{BASE}/tasks/{task1_id}/", json={"title": "Updated task", "priority": "low"}, headers=headers)
    check("Update task", r.status_code == 200 and r.json()["title"] == "Updated task")

    # ==================================================================
    print("\n=== STATUS TRANSITIONS ===")
    # ==================================================================

    # 15. Valid: todo → in_progress
    r = requests.patch(f"{BASE}/tasks/{task1_id}/", json={"status": "in_progress"}, headers=headers)
    check("todo → in_progress", r.status_code == 200 and r.json()["status"] == "in_progress", f"{r.status_code} {r.text}")

    # 16. Valid: in_progress → done
    r = requests.patch(f"{BASE}/tasks/{task1_id}/", json={"status": "done"}, headers=headers)
    check("in_progress → done", r.status_code == 200 and r.json()["status"] == "done", f"{r.status_code} {r.text}")

    # 17. Invalid: done → in_progress (not allowed per our rules)
    r = requests.patch(f"{BASE}/tasks/{task1_id}/", json={"status": "in_progress"}, headers=headers)
    check("done → in_progress blocked", r.status_code == 400, f"{r.status_code} {r.text}")

    # 18. Valid: done → todo (restart task)
    r = requests.patch(f"{BASE}/tasks/{task1_id}/", json={"status": "todo"}, headers=headers)
    check("done → todo (restart)", r.status_code == 200, f"{r.status_code} {r.text}")

    # ==================================================================
    print("\n=== VALIDATION ===")
    # ==================================================================

    # 19. Due date in the past (on create)
    r = requests.post(f"{BASE}/tasks/", json={"title": "Past due", "due_date": "2020-01-01"}, headers=headers)
    check("Past due_date rejected on create", r.status_code == 400, f"{r.status_code} {r.text}")

    # 20. Empty title
    r = requests.post(f"{BASE}/tasks/", json={"title": ""}, headers=headers)
    check("Empty title rejected", r.status_code == 400, f"{r.status_code}")

    # 21. Invalid status value
    r = requests.post(f"{BASE}/tasks/", json={"title": "Bad status", "status": "invalid"}, headers=headers)
    check("Invalid status rejected", r.status_code == 400, f"{r.status_code}")

    # 22. Invalid priority value
    r = requests.post(f"{BASE}/tasks/", json={"title": "Bad priority", "priority": "critical"}, headers=headers)
    check("Invalid priority rejected", r.status_code == 400, f"{r.status_code}")

    # ==================================================================
    print("\n=== FILTERING & SEARCH ===")
    # ==================================================================

    # 23. Filter by status
    r = requests.get(f"{BASE}/tasks/?status=done", headers=headers)
    check("Filter by status=done", r.status_code == 200 and all(t["status"] == "done" for t in r.json()["results"]))

    # 24. Filter by priority
    r = requests.get(f"{BASE}/tasks/?priority=urgent", headers=headers)
    check("Filter by priority=urgent", r.status_code == 200 and all(t["priority"] == "urgent" for t in r.json()["results"]))

    # 25. Filter by category
    r = requests.get(f"{BASE}/tasks/?category={cat_id}", headers=headers)
    check("Filter by category", r.status_code == 200 and all(t["category"] == cat_id for t in r.json()["results"]))

    # 26. Filter overdue
    r = requests.get(f"{BASE}/tasks/?overdue=true", headers=headers)
    check("Filter overdue", r.status_code == 200)
    if r.json()["results"]:
        check("Overdue tasks are overdue", all(t["is_overdue"] for t in r.json()["results"]))
    else:
        check("Overdue tasks are overdue", True)  # no overdue tasks = valid

    # 27. Search
    r = requests.get(f"{BASE}/tasks/?search=Full", headers=headers)
    check("Search by title", r.status_code == 200 and any("Full" in t["title"] for t in r.json()["results"]))

    # 28. CSV filter (multiple statuses)
    r = requests.get(f"{BASE}/tasks/?status=todo,in_progress", headers=headers)
    check("CSV status filter", r.status_code == 200 and all(t["status"] in ("todo", "in_progress") for t in r.json()["results"]))

    # 29. Ordering
    r = requests.get(f"{BASE}/tasks/?ordering=due_date", headers=headers)
    check("Ordering by due_date", r.status_code == 200)

    # ==================================================================
    print("\n=== CROSS-USER ISOLATION ===")
    # ==================================================================

    # 30. Other user cannot access our task
    r = requests.get(f"{BASE}/tasks/{task2_id}/", headers=other_headers)
    check("Cross-user task access blocked", r.status_code == 404, f"{r.status_code}")

    # 31. Other user's task list is empty
    r = requests.get(f"{BASE}/tasks/", headers=other_headers)
    check("Other user sees 0 tasks", r.json()["count"] == 0, f"count={r.json()['count']}")

    # ==================================================================
    print("\n=== TASK STATS ===")
    # ==================================================================

    # 32. Stats endpoint
    r = requests.get(f"{BASE}/tasks/stats/", headers=headers)
    check("Stats endpoint", r.status_code == 200, f"{r.status_code}")
    stats = r.json()
    check("Stats has total", "total" in stats and isinstance(stats["total"], int))
    check("Stats has by_status", "by_status" in stats and "todo" in stats["by_status"])
    check("Stats has by_priority", "by_priority" in stats and "medium" in stats["by_priority"])
    check("Stats has overdue", "overdue" in stats)

    # ==================================================================
    print("\n=== DELETE ===")
    # ==================================================================

    # 33. Delete task
    r = requests.delete(f"{BASE}/tasks/{task1_id}/", headers=headers)
    check("Delete task", r.status_code == 204, f"{r.status_code}")

    # 34. Confirm deleted
    r = requests.get(f"{BASE}/tasks/{task1_id}/", headers=headers)
    check("Deleted task returns 404", r.status_code == 404)

    # 35. Delete category
    r = requests.delete(f"{BASE}/categories/{cat2_id}/", headers=headers)
    check("Delete category", r.status_code == 204, f"{r.status_code}")

    # 36. Unauthenticated access blocked
    r = requests.get(f"{BASE}/tasks/")
    check("Unauthenticated tasks blocked", r.status_code == 401)

    # ==================================================================
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
    if failed:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
