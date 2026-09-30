from test_api import auth_headers, bootstrap_owner, client, create_user  # noqa: F401
from test_balanced_range import wave, BASE
from types import SimpleNamespace
from dataclasses import replace
from market_data.models import CandleDataset, Timeframe
from app_layer.services.balanced_analysis import analyze_balanced
from app_layer.services.playbook import range_touch_preset

def snapshot():
    now=BASE+200*604800000
    def candles(symbol,tf,**kw):
        frame=Timeframe(tf)
        bars=tuple(replace(b,timeframe=frame,timestamp=now-(120-i)*frame.duration_ms) for i,b in enumerate(wave()))
        return CandleDataset(symbol,frame,bars)
    result=analyze_balanced(SimpleNamespace(candles=candles),None,'BTC/USDT','1h',range_touch_preset(),None,'Test',200,now)
    return {**result,'venue':'binance'}

def test_saved_range_private_snapshot_and_review(client):
    root=bootstrap_owner(client); user=create_user(client,root,'range@example.com')
    h=auth_headers(user); snap=snapshot()
    payload=dict(low=90,high=115,notes='Outer reactions',reason='outer_boundaries',snapshot=snap)
    assert client.post('/observed-ranges',json=payload).status_code==401
    response=client.post('/observed-ranges',headers=h,json=payload)
    assert response.status_code==201,response.text
    entry=response.json(); path='/observed-ranges/'+entry['id']
    assert 'snapshot' not in entry
    stored=client.get(path,headers=h).json()
    assert stored['snapshot']['candles']==snap['candles']
    assert stored['high']==115
    assert client.get('/observed-ranges',headers=auth_headers(root)).json()==[]
    assert client.get(path,headers=auth_headers(root)).status_code==404
    assert client.delete(path,headers=auth_headers(root)).status_code==404
    assert client.get('/observed-ranges/review',headers=auth_headers(root)).json()['groups']==[]
    client.post('/observed-ranges',headers=h,json=payload)
    group=client.get('/observed-ranges/review',headers=h).json()['groups'][0]
    assert group['samples']==1 and group['evaluation'] is None
    assert client.post('/observed-ranges',headers=h,json={**payload,'low':120}).status_code==400
    assert client.post('/observed-ranges',headers=h,json={**payload,'owner_user_id':'fake'}).status_code==400
    assert client.delete(path,headers=h).status_code==204
    assert client.get(path,headers=h).status_code==404

def test_learning_check_uses_earlier_labels_only(client):
    root=bootstrap_owner(client);h=auth_headers(root);snap=snapshot()
    lo,hi=snap['range']['low'],snap['range']['high'];width=hi-lo
    for i in range(10):
        snap['freshness']['last_closed_timestamp_ms']=BASE+i*3600000
        delta=.1 if i<7 else .4
        payload=dict(low=lo,high=hi+delta*width,snapshot=snap)
        assert client.post('/observed-ranges',headers=h,json=payload).status_code==201
    review=client.get('/observed-ranges/review',headers=h).json()
    assert review['automatic_adaptation'] is False
    result=review['groups'][0]['evaluation']
    assert result['training_examples']==7 and result['held_out_examples']==3
    assert abs(result['high_offset']-.1)<1e-8
    assert abs(result['adjusted_error']-.15)<1e-8
