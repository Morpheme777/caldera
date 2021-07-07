import pytest
from aiohttp import web

from app.service.auth_svc import AuthService, HEADER_API_KEY, CONFIG_API_KEY_RED, COOKIE_SESSION
from app.service.file_svc import FileSvc
from app.utility.base_world import BaseWorld
from app.api.v2.handlers.fact_api import FactApi
from app.api.v2.responses import json_request_validation_middleware
from app.api.v2.security import authentication_required_middleware_factory
from app.objects.secondclass.c_fact import wildcard_string
from app.service.knowledge_svc import KnowledgeService

cakr = 'abc123'
headers = {'key': cakr, 'Content-Type': 'application/json'}

@pytest.fixture
def base_world():

    BaseWorld.apply_config(
        name='main',
        config={
            CONFIG_API_KEY_RED: cakr,

            'users': {
                'red': {'reduser': 'redpass'},
                'blue': {'blueuser': 'bluepass'}
            },

            'crypt_salt': 'thisisdefinitelynotkosher',  # Salt for file service instantiation
            'encryption_key': 'andneitheristhis'  # fake encryption key for file service instantiation
        }
    )

    yield BaseWorld
    BaseWorld.clear_config()


@pytest.fixture
def knowledge_webapp(loop, app_svc, base_world, data_svc):
    link = app_svc(loop)
    link.add_service('auth_svc', AuthService())
    link.add_service('knowledge_svc', KnowledgeService())
    link.add_service('file_svc', FileSvc())  # This needs to be done this way, or it won't boot due to not having
                                                 # a valid base world configuration
    services = link.get_services()
    app = web.Application(
        middlewares=[
            authentication_required_middleware_factory(services['auth_svc']),
            json_request_validation_middleware
        ]
    )

    FactApi(services).add_routes(app)

    return app


async def test_display_facts(knowledge_webapp, aiohttp_client):
    client = await aiohttp_client(knowledge_webapp)

    fact_data = {
        'trait': 'demo',
        'value': 'test'
    }
    await client.post('/facts', json=fact_data, headers=headers)
    resp = await client.get('/facts', json=fact_data, headers=headers)
    data = await resp.json()
    response = data['found']

    assert len(response) == 1
    assert response[0]['trait'] == 'demo'
    assert response[0]['value'] == 'test'
    assert response[0]['source'] == wildcard_string


async def test_display_relationships(knowledge_webapp, aiohttp_client):
    client = await aiohttp_client(knowledge_webapp)
    op_id_test = 'this_is_a_valid_operation_id'
    fact_data_a = {
        'trait': 'a',
        'value': '1',
    }
    fact_data_b = {
        'trait': 'b',
        'value': '2'
    }
    relationship_data = {
        'source': fact_data_a,
        'edge': 'gamma',
        'target': fact_data_b,
        'origin': op_id_test
    }
    await client.post('/relationships', json=relationship_data, headers=headers)
    resp = await client.get('/relationships', json=relationship_data, headers=headers)
    data = await resp.json()
    response = data['found']

    assert len(response) == 1
    assert response[0]['source']['trait'] == 'a'
    assert response[0]['source']['value'] == '1'
    assert response[0]['edge'] == 'gamma'
    assert response[0]['origin'] == 'this_is_a_valid_operation_id'
    assert response[0]['source']['source'] == 'this_is_a_valid_operation_id'


async def test_remove_fact(knowledge_webapp, aiohttp_client):
    client = await aiohttp_client(knowledge_webapp)
    fact_data = {
        'trait': 'demo',
        'value': 'test'
    }
    init = await client.post('/facts', json=fact_data, headers=headers)
    pre = await init.json()
    subs = await client.delete('/facts', json=fact_data, headers=headers)
    post = await subs.json()
    tmp = await client.get('/facts', json=fact_data, headers=headers)
    cur = await tmp.json()
    current = cur['found']
    start = pre['added']
    end = post['removed']
    assert len(start) == 1
    assert len(end) == 1
    assert len(current) == 0
    assert start == end


async def test_remove_relationship(knowledge_webapp, aiohttp_client):
    client = await aiohttp_client(knowledge_webapp)
    op_id_test = 'this_is_a_valid_operation_id'
    fact_data_a = {
        'trait': 'a',
        'value': '1',
    }
    fact_data_b = {
        'trait': 'b',
        'value': '2'
    }
    relationship_data = {
        'source': fact_data_a,
        'edge': 'alpha',
        'target': fact_data_b,
        'origin': op_id_test
    }
    init = await client.post('/relationships', json=relationship_data, headers=headers)
    pre = await init.json()
    subs = await client.delete('/relationships', json=dict(edge='alpha'), headers=headers)
    post = await subs.json()
    resp = await client.get('/relationships', json=relationship_data, headers=headers)
    cur = await resp.json()
    start = pre['added']
    end = post['removed']
    current = cur['found']
    assert len(start) == 1
    assert len(end) == 1
    assert len(current) == 0
    assert start == end


async def test_add_fact(knowledge_webapp, aiohttp_client):
    client = await aiohttp_client(knowledge_webapp)

    fact_data = {
        'trait': 'demo',
        'value': 'test'
    }
    resp = await client.post('/facts', json=fact_data, headers=headers)
    data = await resp.json()
    response = data['added']
    assert len(response) == 1
    assert response[0]['trait'] == 'demo'
    assert response[0]['value'] == 'test'

    tmp = await client.get('/facts', json=fact_data, headers=headers)
    cur = await tmp.json()
    current = cur['found']
    assert current == response


async def test_add_relationship(knowledge_webapp, aiohttp_client):
    client = await aiohttp_client(knowledge_webapp)
    fact_data_a = {
        'trait': 'a',
        'value': '1',
    }
    fact_data_b = {
        'trait': 'b',
        'value': '2'
    }
    relationship_data = {
        'source': fact_data_a,
        'edge': 'tango',
        'target': fact_data_b
    }
    expected_response = f"{fact_data_a['trait']}({fact_data_a['value']}) : " \
                        f"tango : {fact_data_b['trait']}({fact_data_b['value']})"
    resp = await client.post('/relationships', json=relationship_data, headers=headers)
    data = await resp.json()
    response = data['added']
    assert len(response) == 1
    assert response[0]['source']['trait'] == fact_data_a['trait']
    assert response[0]['target']['value'] == fact_data_b['value']
    assert response[0]['edge'] == 'tango'
    assert response[0]['source']['relationships'] == response[0]['target']['relationships']
    assert response[0]['source']['relationships'][0] == expected_response

    resp = await client.get('/relationships', json=relationship_data, headers=headers)
    cur = await resp.json()
    current = cur['found']
    assert current == response


async def test_patch_fact(knowledge_webapp, aiohttp_client):
    client = await aiohttp_client(knowledge_webapp)
    fact_data = {
        'trait': 'domain.user.name',
        'value': 'thomas'
    }
    patch_data = {
        "criteria": {
            "trait": "domain.user.name",
            "value": "thomas"},
        "updates": {
            "value": "jacobson"
        }
    }
    await client.post('/facts', json=fact_data, headers=headers)
    resp = await client.patch('/facts', json=patch_data, headers=headers)
    message = await resp.json()
    patched = message['updated']
    assert len(patched) == 1
    assert patched[0]['value'] == 'jacobson'

    tmp = await client.get('/facts', json=dict(trait='domain.user.name'), headers=headers)
    cur = await tmp.json()
    current = cur['found']
    assert len(current) == 1
    assert patched == current


async def test_patch_relationship(knowledge_webapp, aiohttp_client):
    client = await aiohttp_client(knowledge_webapp)
    relationship_data = {
        "source": {
            "trait": "domain.user.name",
            "value": "bobross"
        },
        "edge": "has_password",
        "target": {
            "trait": "domain.user.password",
            "value": "12345"
        }
    }
    patch_data = {
        "criteria": {
            "edge": "has_password",
            "source": {
                "value": "bobross"
            }
        },
        "updates": {
            "target": {
                "value": "54321"
            },
            "edge": "has_admin_password"
        }
    }
    await client.post('/relationships', json=relationship_data, headers=headers)
    resp = await client.patch('/relationships', json=patch_data, headers=headers)
    message = await resp.json()
    patched = message['updated']
    assert len(patched) == 1
    assert patched[0]['target']['value'] == '54321'
    assert patched[0]['source']['value'] == 'bobross'
    assert patched[0]['edge'] == 'has_admin_password'

    tmp = await client.get('/relationships', json=dict(edge='has_admin_password'), headers=headers)
    cur = await tmp.json()
    current = cur['found']
    assert len(current) == 1
    assert patched == current
