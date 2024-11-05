from idlelib.mainmenu import menudefs
from queue import Empty
from wcferry import Wcf, WxMsg
import logging
import requests
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 阿里百炼密钥
access_token = "x'x'x'x'x"
# 高德地图 API 密钥
AMAP_API_KEY = "xxxxxx"

# 检查访问密钥是否正确读取
if not access_token:
    raise ValueError("请确保设置了 ALIYUN_ACCESS_TOKEN 环境变量")

# 角色和权限定义
ROLES = {
    "admin": ["add_new_administrator", "del_chatroom_members", "list_administrators", "remove_administrator"],
}

# 用户和角色映射
USER_ROLES = {
    "wxid-xxxxx": "admin"
}


def add_new_admin(wxid, new_admin_wxid):
    """添加新的管理员"""
    if wxid in USER_ROLES and USER_ROLES[wxid] == "admin":
        USER_ROLES[new_admin_wxid] = "admin"
        logging.info(f"用户 {new_admin_wxid} 已被设置为管理员")
        return True
    else:
        logging.warning(f"用户 {wxid} 尝试添加新管理员但无权限。")
        return False


def del_chatroom_members(wcf, roomid, wxids):
    """删除群成员"""
    if wxids:
        # 防止管理员踢出其他管理员
        non_admin_wxids = [wxid for wxid in wxids if wxid not in USER_ROLES or USER_ROLES[wxid] != "admin"]
        if non_admin_wxids:
            result = wcf.del_chatroom_members(roomid=roomid, wxids=non_admin_wxids)
            if result == 1:
                logging.info(f"成功踢出成员: {non_admin_wxids}")
                return True
            else:
                logging.warning(f"踢出成员失败: {non_admin_wxids}")
                return False
        else:
            logging.warning("尝试踢出的成员都是管理员，操作失败。")
            return False
    else:
        logging.warning("没有指定要踢出的成员。")
        return False


def remove_administrator(wxid, target_name, chatroom_members):
    """通过名称删除管理员"""
    if wxid in USER_ROLES and USER_ROLES[wxid] == "admin":
        target_wxid = get_member_wxid(chatroom_members, target_name)
        if target_wxid and target_wxid in USER_ROLES and USER_ROLES[target_wxid] == "admin":
            del USER_ROLES[target_wxid]
            logging.info(f"用户 {target_name} (wxid: {target_wxid}) 已被移除管理员")
            return True
        else:
            logging.warning(f"用户 {target_name} 不是管理员或不存在。")
            return False
    else:
        logging.warning(f"用户 {wxid} 尝试删除管理员但无权限。")
        return False


# 初始化微信客户端
def initialize_wcf():
    wcf = Wcf()
    logging.info("微信客户端已初始化")
    return wcf


# 调用阿里云百炼AI接口获取回复内容
def call_bailian_ai(text):
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": text}],
        "enable_search": True
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # 检查请求是否成功
        response_json = response.json()
        ai_response = response_json.get('choices', [{}])[0].get('message', {}).get('content', '无法获取回复')
        return ai_response
    except Exception as e:
        logging.error(f"调用阿里云百炼AI接口失败: {e}")
        return "无法获取回复"


def get_weather(city="330100"):
    url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={city}&key={AMAP_API_KEY}&extensions=base"
    response = requests.get(url)
    data = response.json()
    logging.info(f"高德地图天气 API 响应: {data}")  # 打印 API 响应内容

    if data["status"] == "1" and data["infocode"] == "10000":
        if "lives" in data and data["lives"]:
            lives = data["lives"][0]
            weather_info = f"城市: {lives['city']}\n天气: {lives['weather']}\n温度: {lives['temperature']}°C\n风向: {lives['winddirection']}\n风力: {lives['windpower']}级\n湿度: {lives['humidity']}%\n发布时间: {lives['reporttime']}"
            return weather_info
        else:
            return "无法获取实时天气信息，请稍后再试。"
    else:
        return "无法获取天气信息，请稍后再试。"


# 获取微信登录信息
def get_user_info(wcf):
    user_info = wcf.get_user_info()
    logging.info(f"用户名: {user_info.get('name', '未知')},用户ID: {user_info.get('wxid', '未知')}")
    return user_info


def remove_at_name(message):
    """ 移除消息中的 '@' 名称 """
    return re.sub(r'@\S+\s*', '', message).strip()


def processMsg(msg: WxMsg):
    if msg.from_group():
        # 清洗消息内容
        clean_content = remove_at_name(msg.content)
        return clean_content
    else:
        return msg.content


def get_member_name(chatroom_members, wxid):
    """通过 wxid 获取群聊成员的名称"""
    return chatroom_members.get(wxid, "未知")


def get_member_wxid(chatroom_members, name):
    """通过名称获取群聊成员的 wxid"""
    for wxid, member_name in chatroom_members.items():
        if member_name == name:
            return wxid
    return None


def check_permission(wxid, permission):
    role = USER_ROLES.get(wxid)
    if role and permission in ROLES.get(role, []):
        return True
    return False


def list_administrators(wcf, msg, chatroom_members=None):
    """列出所有管理员"""
    admin_list = [f"{get_member_name(chatroom_members, wxid)} (wxid: {wxid})" for wxid, role in USER_ROLES.items() if
                  role == "admin"]
    admin_list_str = "\n".join(admin_list)
    if msg.from_group():
        sender_name = get_member_name(chatroom_members, msg.sender)
        wcf.send_text(f"@{sender_name} 当前管理员名单:\n{admin_list_str}", msg.roomid, aters=msg.sender)
    else:
        wcf.send_text(f"当前管理员名单:\n{admin_list_str}", msg.sender)


def handle_messages(wcf):
    wcf.enable_receiving_msg()
    logging.info("开始接收消息")

    while wcf.is_receiving_msg():
        try:
            msg = wcf.get_msg()
            """ 获取群成员列表 得到wxid和name """
            chatroom_members = wcf.get_chatroom_members(msg.roomid) if msg.from_group() else None
            """ 通过 wxid 获取群聊成员的名称 """
            sender_name = get_member_name(chatroom_members, msg.sender) if msg.from_group() else "私聊用户"

            if msg.from_group():
                logging.info(f"收到群聊消息: {msg.content} 来自 {msg.roomid}")
                clean_content = processMsg(msg)
                logging.info(f"清洗后的内容: {clean_content}")  # 调试信息
                if msg.is_at(wcf.get_user_info()["wxid"]):
                    if clean_content.strip() == "查看天气":
                        weather_info = get_weather()
                        at_message = f"@{sender_name} {weather_info}"
                        wcf.send_text(at_message, msg.roomid, aters=msg.sender)
                        logging.info(f"发送天气信息给 {msg.sender}: {weather_info}")
                    elif clean_content.strip().startswith("踢 "):
                        parts = clean_content.split(maxsplit=1)
                        if len(parts) > 1:
                            target_name = parts[1].strip()
                            target_wxid = get_member_wxid(chatroom_members, target_name)
                            if target_wxid:
                                if check_permission(msg.sender, "del_chatroom_members"):
                                    if del_chatroom_members(wcf, msg.roomid, [target_wxid]):
                                        wcf.send_text(f"@{sender_name} 成功踢出了 {target_name}", msg.roomid,
                                                      aters=msg.sender)
                                    else:
                                        wcf.send_text(f"@{sender_name} 踢出失败，请重试。", msg.roomid, aters=msg.sender)
                                else:
                                    wcf.send_text(f"@{sender_name} 您没有权限执行此操作。", msg.roomid, aters=msg.sender)
                            else:
                                wcf.send_text(f"@{sender_name} 未找到名为 {target_name} 的成员。", msg.roomid,
                                              aters=msg.sender)
                        else:
                            wcf.send_text(f"@{sender_name} 格式错误，请使用：踢 <成员名称>", msg.roomid, aters=msg.sender)
                    elif clean_content.strip().startswith("添加管理员 "):
                        parts = clean_content.split(maxsplit=1)
                        if len(parts) > 1:
                            target_name = parts[1].strip()
                            target_wxid = get_member_wxid(chatroom_members, target_name)
                            if target_wxid:
                                if check_permission(msg.sender, "add_new_administrator"):
                                    if add_new_admin(msg.sender, target_wxid):
                                        wcf.send_text(f"@{sender_name} 用户 {target_name} 已被设置为管理员。",
                                                      msg.roomid, aters=msg.sender)
                                    else:
                                        wcf.send_text(f"@{sender_name} 添加管理员失败。", msg.roomid, aters=msg.sender)
                                else:
                                    wcf.send_text(f"@{sender_name} 您没有权限执行此操作。", msg.roomid, aters=msg.sender)
                            else:
                                wcf.send_text(f"@{sender_name} 未找到名为 {target_name} 的成员。", msg.roomid,
                                              aters=msg.sender)
                        else:
                            wcf.send_text(f"@{sender_name} 格式错误，请使用：添加管理员 <成员名称>", msg.roomid,
                                          aters=msg.sender)
                    elif clean_content.strip().startswith("删除管理员 "):
                        parts = clean_content.split(maxsplit=1)
                        if len(parts) > 1:
                            target_name = parts[1].strip()
                            if check_permission(msg.sender, "remove_administrator"):
                                if remove_administrator(msg.sender, target_name, chatroom_members):
                                    wcf.send_text(f"@{sender_name} 用户 {target_name} 已被移除管理员。", msg.roomid,
                                                  aters=msg.sender)
                                else:
                                    wcf.send_text(f"@{sender_name} 删除管理员失败。", msg.roomid, aters=msg.sender)
                            else:
                                wcf.send_text(f"@{sender_name} 您没有权限执行此操作。", msg.roomid, aters=msg.sender)
                        else:
                            wcf.send_text(f"@{sender_name} 格式错误，请使用：删除管理员 <成员名称>", msg.roomid,
                                          aters=msg.sender)
                    elif clean_content.strip() == "列出管理员":
                        if check_permission(msg.sender, "list_administrators"):
                            list_administrators(wcf, msg, chatroom_members)
                        else:
                            wcf.send_text(f"@{sender_name} 您没有权限执行此操作。", msg.roomid, aters=msg.sender)
                    else:
                        ai_response = call_bailian_ai(clean_content)
                        at_message = f"@{sender_name} {ai_response}"
                        wcf.send_text(at_message, msg.roomid, aters=msg.sender)
                        logging.info(f"发送AI回复给 {msg.roomid}: {at_message}")
                elif should_send_emotion(clean_content):
                    wcf.send_emotion("D:/Wechat/Wechat/photo/pate.png", msg.roomid)
                    logging.info(f"拍一拍消息发送成功给用户 {msg.sender}")
            else:
                logging.info(f"收到私聊消息: {msg.content} 来自 {msg.sender}")
                if msg.content == "#帮助":
                    wcf.send_text("1、添加管理员\n2、查看天气\n3、列出管理员\n4、删除管理员", msg.sender)
                elif msg.content == "查看天气":
                    weather_info = get_weather()
                    wcf.send_text(weather_info, msg.sender)
                    logging.info(f"发送天气信息给 {msg.sender}: {weather_info}")
                elif msg.type == 34:
                    wcf.send_text("语音识别正在开发...", msg.sender)
                    logging.info(f"收到语音,已保存{msg.id}")
                elif msg.type == 37:
                    if check_permission(msg.sender, "accept_friend_request"):
                        wcf.send_text(f"有一个好友申请！", receiver="wxid_u33r6n1yegsh22")
                elif msg.content.startswith("添加管理员 "):
                    parts = msg.content.split(maxsplit=1)
                    if len(parts) > 1:
                        target_name = parts[1].strip()
                        target_wxid = get_member_wxid(chatroom_members, target_name)
                        if target_wxid:
                            if check_permission(msg.sender, "add_new_administrator"):
                                if add_new_admin(msg.sender, target_wxid):
                                    wcf.send_text(f"用户 {target_name} 已被设置为管理员。", msg.sender)
                                else:
                                    wcf.send_text("添加管理员失败。", msg.sender)
                            else:
                                wcf.send_text("您没有权限添加管理员。", msg.sender)
                        else:
                            wcf.send_text(f"未找到名为 {target_name} 的成员。", msg.sender)
                    else:
                        wcf.send_text("格式错误，请使用：添加管理员 <成员名称>", msg.sender)
                elif msg.content.startswith("删除管理员 "):
                    parts = msg.content.split(maxsplit=1)
                    if len(parts) > 1:
                        target_name = parts[1].strip()
                        if check_permission(msg.sender, "remove_administrator"):
                            if remove_administrator(msg.sender, target_name, chatroom_members):
                                wcf.send_text(f"用户 {target_name} 已被移除管理员。", msg.sender)
                            else:
                                wcf.send_text("删除管理员失败。", msg.sender)
                        else:
                            wcf.send_text("您没有权限删除管理员。", msg.sender)
                    else:
                        wcf.send_text("格式错误，请使用：删除管理员 <成员名称>", msg.sender)
                elif msg.content == "列出管理员":
                    if check_permission(msg.sender, "list_administrators"):
                        list_administrators(wcf, msg)
                    else:
                        wcf.send_text("您没有权限执行此操作。", msg.sender)
                elif should_send_emotion(msg.content):
                    wcf.send_text("拍一拍消息发送成功给用户 {msg.sender}")
                else:
                    ai_response = call_bailian_ai(msg.content)
                    wcf.send_text(ai_response, msg.sender)
                    logging.info(f"发送AI回复给 {msg.sender}: {ai_response}")

            # 处理进群和退群事件
            if msg.type == 10000:  # 进群事件
                new_member_wxid = msg.content.split(":")[1].strip()
                new_member_name = get_member_name(chatroom_members, new_member_wxid)
                welcome_message = f"欢迎 {new_member_name} 加入群聊！"
                wcf.send_text(welcome_message, msg.roomid)
                logging.info(f"发送欢迎消息: {welcome_message}")
            elif msg.type == 10002:  # 退群事件
                left_member_wxid = msg.content.split(":")[1].strip()
                left_member_name = get_member_name(chatroom_members, left_member_wxid)
                leave_message = f"{left_member_name} 退出了群聊。"
                wcf.send_text(leave_message, msg.roomid)
                logging.info(f"发送退群消息: {leave_message}")

        except Empty:
            continue
        except Exception as e:
            logging.error(f"处理消息时发生错误: {e}")


def should_send_emotion(content):
    """判断是否需要发送拍一拍表情"""
    return "拍了拍我" in content


def main():
    wcf = initialize_wcf()
    get_user_info(wcf)
    handle_messages(wcf)
    wcf.keep_running()


if __name__ == "__main__":
    main()
