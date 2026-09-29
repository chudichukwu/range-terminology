from test_api import auth_headers, bootstrap_owner, client, create_user  # noqa: F401

NOTE = {"title": "BTC range", "body": "Wait for a reclaim", "category": "trade_plan", "symbol": "BTC", "timeframe": "1h"}

def test_private_journal_crud(client):
    assert client.get('/journal').status_code == 401
    root = bootstrap_owner(client)
    user = create_user(client, root, 'journal@example.com')
    h = auth_headers(user)
    response = client.post('/journal', headers=h, json=NOTE)
    assert response.status_code == 201
    entry = response.json()
    path = '/journal/' + entry['id']
    assert client.get('/journal', headers=h).json()[0]['body'] == NOTE['body']
    assert client.get('/journal', headers=auth_headers(root)).json() == []
    for other in [auth_headers(root), auth_headers(create_user(client, root, 'second@example.com'))]:
        assert client.put(path, headers=other, json=NOTE).status_code == 404
        assert client.delete(path, headers=other).status_code == 404
    updated = client.put(path, headers=h, json={**NOTE, 'body': 'Reclaimed; review tomorrow'})
    assert updated.status_code == 200
    assert updated.json()['created_at_ms'] == entry['created_at_ms']
    assert client.get('/journal', headers=h).json()[0]['body'] == 'Reclaimed; review tomorrow'
    assert client.post('/journal', headers=h, json={**NOTE, 'title':'   '}).status_code == 400
    assert client.post('/journal', headers=h, json={**NOTE, 'owner_user_id':'fake'}).status_code == 400
    assert client.delete(path, headers=h).status_code == 204
    assert client.get('/journal', headers=h).json() == []

def test_all_admin_routes_reject_non_owner(client):
    root = bootstrap_owner(client)
    user = create_user(client, root, 'ordinary@example.com')
    for route, operations in client.app.openapi()['paths'].items():
        if not route.startswith('/admin'):
            continue
        path = route.replace('{user_id}', 'any-user')
        for method in operations:
            assert client.request(method, path, json={}, headers=auth_headers(user)).status_code == 403
            assert client.request(method, path, json={}).status_code == 401
