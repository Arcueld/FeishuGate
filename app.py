import threading
import os
import json
import hashlib

from tools import *

import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from lark_oapi.api.application.v6 import *
from lark_oapi.api.drive.v1 import *
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger,
    P2CardActionTriggerResponse,
)

group_id = os.getenv("GROUP_ID")
PERMISSION_CARD_ID = os.getenv("PERMISSION_CARD_ID")
appid = os.getenv("APP_ID")
app_secret = os.getenv("APP_SECRET")

client = lark.Client.builder().app_id(lark.APP_ID).app_secret(lark.APP_SECRET).build()

def send_message(receive_id_type, receive_id, msg_type, content):
    request = (
        CreateMessageRequest.builder()
        .receive_id_type(receive_id_type)
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type(msg_type)
            .content(content)
            .build()
        )
        .build()
    )
    response = client.im.v1.message.create(request)
    if not response.success():
        raise Exception(
            f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
        )
    return response

def send_permission_card(receive_id_type, receive_id, index):
    data_basic_info= fetch_data_basic_info(index)[0]
    send_time, privilege, username, hostname, external_ip = data_basic_info

    data_env_info = fetch_data_env_info(index)[0]
    core_num, ram, resolution, current_path, parent_process, boot_time, tempfile_num = data_env_info

    try:
        from api import get_sandbox_analysis
        sandbox_result = get_sandbox_analysis(index)
        print(f"是否沙箱: {sandbox_result['is_sandbox']}")
        print(f"置信度: {sandbox_result['confidence_score']}%")
        print(f"详细分析: {sandbox_result['analysis']}")
        
        # 如果是沙箱且置信度大于等于60，禁用准入按钮
        access_is_disabled = str(sandbox_result['is_sandbox']) == "True" and int(sandbox_result['confidence_score']) >= 60
        
        # 根据沙箱检测结果自动执行准入/拒绝
        if access_is_disabled:
            insert_payload(index, False)
            print(f"自动拒绝: 检测到沙箱环境 (置信度: {sandbox_result['confidence_score']}%)")
        else:
            print(f"等待人工决断: 未检测到沙箱环境或置信度不足")
            
    except (ValueError, Exception) as e:
        print(f"沙箱检测失败: {str(e)}")
        sandbox_result = {
            'is_sandbox': "null",
            'confidence_score': "null",
            'analysis': "null"
        }
        access_is_disabled = False

    content = json.dumps(
        {
            "type": "template",
            "data": {
                "template_id": PERMISSION_CARD_ID,
                "template_variable": {
                    "send_time": send_time,
                    "privilege": privilege,
                    "username": username,
                    "hostname": hostname,
                    "external_ip": external_ip,
                    "index": index,
                    "core_num": core_num,
                    "ram": ram,
                    "resolution": resolution,
                    "current_path": current_path,
                    "parent_process": parent_process,
                    "boot_time": boot_time,
                    "is_sandbox": str(sandbox_result['is_sandbox']),
                    "confidence_score": str(sandbox_result['confidence_score']),
                    "analysis": str(sandbox_result['analysis']),
                    "access_is_disabled": access_is_disabled
                },
            },
        }
    )
    return send_message(receive_id_type, receive_id, "interactive", content)

recent_send_times = set()

def do_p2_drive_file_edit_v1(data: lark.drive.v1.P2DriveFileEditV1) -> None:

    index = fetch_data_index()
    recv_data = fetch_data_basic_info(index)[0]
    send_time = recv_data[0]
    
    if send_time in recent_send_times:
        print(f"ignore duplicate event {send_time}")
        return        
    else:
        recent_send_times.add(send_time)

    # 防抖动
    try:
        send_permission_card("chat_id", group_id, index)
    except:
        pass

def do_card_action_trigger(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    recv_data = json.loads(lark.JSON.marshal(data))
    action = recv_data["event"]["action"]["value"]["action"]
    
    index = int(recv_data["event"]["action"]["value"]["index"])



    if action == "access":
        insert_payload(index, True)
        resp = {
            "toast": {
                "type": "success",
                "content": "已准入",
                "card":{
                    "type": "template",
                    "data": {
                        "template_id": PERMISSION_CARD_ID,
                        "template_variable": {
                            "button_is_disabled": True,
                        },
                    },
                }
            }
        }
    elif action == "deny":
        insert_payload(index, False)

        resp = {
            "toast": {
                "type": "success",
                "content": "已拒绝",
                "card":{ 
                    "type": "template",
                    "data": {
                        "template_id": PERMISSION_CARD_ID,
                        "template_variable": {
                            "button_is_disabled": True,
                        },
                    },
                }
            }
        }

    return P2CardActionTriggerResponse(resp)

event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_drive_file_edit_v1(do_p2_drive_file_edit_v1)
    .register_p2_card_action_trigger(do_card_action_trigger) 
    .build()
)

wsClient = lark.ws.Client(
    lark.APP_ID,
    lark.APP_SECRET,
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
)
hash_to_index = {}

def run_bot():
    wsClient.start()

def main():
    reset_index()
    claer_table()
    initialize()  
    
    run_bot()

if __name__ == "__main__":
    main()