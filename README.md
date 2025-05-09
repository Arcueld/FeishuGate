# 基于飞书bot的准入平台

Python3.10+ 

这里将bot和server写到一块了, 实际上只要一个bot就行 有空再改

因为不是正经开发,仅是基本功能实现 BUG很多

## 准入逻辑

大体流程如下

当`loader`客户端上线后,会主动访问部署在VPS上的服务端接口,上传本机的硬件及环境信息

服务端收到客户端信息后,会将数据写入飞书云文档中,作为准入判断的基础数据源

Bot实时监听该文档的变更事件,一旦发现数据变更（即有客户端请求准入）便向指定群聊发送卡片

点击按钮后,会触发机器人后端的回调接口,记录判断结果并更新云文档中的准入状态字段

若确认准入,Bot会将加密后的shellcode填入对应表格字段 等待`loader`拉取

`loader`定时读取云文档中对应的准入状态与下发数据



因为多写了server 这里还走了两次vps 实际上完全可以不走的 这里为实现方便起见就先走vps了

如果纯走云文档通信 那么记得及时的删除bot以重置bot的`app_id`

## 使用方法

1. 创建飞书云文档

2. 根据文档先创建一个卡片机器人 https://open.feishu.cn/app 

3. 给机器人加权限 批量导入权限 复制`privilege.json`内的内容 批量导入(这里给了很多额外没需求的权限 要去掉自己看看), 然后在云文档处给机器人权限(添加文档应用、管理协作者)

4. 订阅事件 `文件编辑`  订阅回调 `卡片回传交互`

5. 创建卡片 https://open.feishu.cn/cardkit/ 导入`card.json` 创建完后记得发布卡片

6. 创建完机器人后在`start.sh` 填写对应的属性
+ APP_ID: 

+ APP_SECRET: 

+ PERMISSION_CARD_ID: 卡片ID

+ WIKI_TOKEN: 

+ GROUP_ID: 群聊ID 在这获取 https://open.feishu.cn/document/server-docs/group/chat-member/add_managers 

7. 运行`start.sh` 
    
    至此bot端就算完成了 client的话自己写(  

    loader只需要访问对应的接口就行了

## 效果

![image-20250507191629694](https://img-host-arcueid.oss-cn-hangzhou.aliyuncs.com/img202505071916749.png)

![image-20250507143816355](https://img-host-arcueid.oss-cn-hangzhou.aliyuncs.com/img202505071438428.png)

![image-20250509162014724](https://img-host-arcueid.oss-cn-hangzhou.aliyuncs.com/img202505091620940.png)