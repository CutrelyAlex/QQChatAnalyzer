from __future__ import annotations

from enum import IntEnum


# NTMsgType - QQ 主消息类型
class NTMsgType(IntEnum):
    KMSGTYPEUNKNOWN = 0  # 未知消息 (type_0)
    KMSGTYPENULL = 1  # 空消息 (type_1 文本)
    KMSGTYPEMIX = 2  # 混合消息（文本+图片等） (type_1 文本)
    KMSGTYPEFILE = 3  # 文件消息 (type_8)
    KMSGTYPESTRUCT = 4  # 结构化消息（JSON 卡片） (type_7)
    KMSGTYPEGRAYTIPS = 5  # 灰色提示/系统消息 (type_1 系统)
    KMSGTYPEPTT = 6  # 语音 (Push To Talk) (type_6)
    KMSGTYPEVIDEO = 7  # 视频 (type_9)
    KMSGTYPEMULTIMSGFORWARD = 8  # 合并转发 (type_11)
    KMSGTYPEREPLY = 9  # 回复 (type_3)
    KMSGTYPEWALLET = 10  # 红包/钱包 (type_10)
    KMSGTYPEARKSTRUCT = 11  # Ark 结构化卡片 (type_7)
    KMSGTYPESTRUCTLONGMSG = 12  # 长消息结构 (type_12)
    KMSGTYPEGIPHY = 13  # Giphy 动图 (type_13)
    KMSGTYPEGIFT = 14  # 礼物消息 (type_14)
    KMSGTYPETEXTGIFT = 15  # 文字礼物 (type_15)
    KMSGTYPEONLINEFILE = 21  # 在线文件 (type_21)
    KMSGTYPEFACEBUBBLE = 24  # 表情气泡 (type_24)
    KMSGTYPESHARELOCATION = 25  # 位置分享/联系人卡片 (type_17)
    KMSGTYPEONLINEFOLDER = 27  # 在线文件夹 (type_27)
    KMSGTYPEPROLOGUE = 29  # 开场白消息 (type_29)


## ElementType - 消息内部元素
class ElementType(IntEnum):
    UNKNOWN = 0  # 未知元素
    TEXT = 1  # 文本
    PIC = 2  # 图片
    FILE = 3  # 文件
    PTT = 4  # 语音
    VIDEO = 5  # 视频
    FACE = 6  # QQ 表情
    REPLY = 7  # 回复引用
    GreyTip = 8  # 灰色提示（拍一拍/撤回等）
    WALLET = 9  # 红包/钱包
    ARK = 10  # Ark 卡片
    MFACE = 11  # 商城表情
    LIVEGIFT = 12  # 直播礼物
    STRUCTLONGMSG = 13  # 长消息结构
    MARKDOWN = 14  # Markdown
    GIPHY = 15  # Giphy 动图
    MULTIFORWARD = 16  # 合并转发
    INLINEKEYBOARD = 17  # 内联键盘
    INTEXTGIFT = 18  # 文内礼物
    CALENDAR = 19  # 日历
    YOLOGAMERESULT = 20  # YOLO 游戏结果
    AVRECORD = 21  # 音视频通话记录
    FEED = 22  # 动态
    TOFURECORD = 23  # 豆腐记录
    ACEBUBBLE = 24  # ACE 气泡
    ACTIVITY = 25  # 活动
    TOFU = 26  # 豆腐
    FACEBUBBLE = 27  # 表情气泡
    SHARELOCATION = 28  # 位置分享
    TASKTOPMSG = 29  # 置顶任务消息
    RECOMMENDEDMSG = 43  # 推荐消息
    ACTIONBAR = 44  # 操作栏


### ChatType - 聊天类别
class ChatType(IntEnum):
    KCHATTYPEUNKNOWN = 0  # 未知
    KCHATTYPEC2C = 1  # 私聊
    KCHATTYPEGROUP = 2  # 群聊
    KCHATTYPEDISC = 3  # 讨论组
    KCHATTYPEGUILD = 4  # 频道
    KCHATTYPEBUDDYNOTIFY = 5  # 好友通知
    KCHATTYPEGROUPNOTIFY = 6  # 群通知
    KCHATTYPEGROUPHELPER = 7  # 群助手
    KCHATTYPEDATALINE = 8  # 数据线
    KCHATTYPEGROUPGUILD = 9  # 群频道
    KCHATTYPEGUILDMETA = 16  # 频道元数据
    KCHATTYPEWEIYUN = 40  # 微云
    KCHATTYPEFAV = 41  # 收藏
    KCHATTYPEADELIE = 42  # Adelie
    KCHATTYPETEMPC2CFROMUNKNOWN = 99  # 临时会话（未知来源）
    KCHATTYPETEMPC2CFROMGROUP = 100  # 临时会话（来自群）
    KCHATTYPETEMPFRIENDVERIFY = 101  # 临时会话（好友验证）
    KCHATTYPETEMPBUSSINESSCRM = 102  # 临时会话（商业CRM）
    KCHATTYPETEMPPUBLICACCOUNT = 103  # 临时会话（公众号）
    KCHATTYPEMATCHFRIEND = 104  # 匹配好友
    KCHATTYPEGAMEMESSAGE = 105  # 游戏消息
    KCHATTYPENEARBY = 106  # 附近的人
    KCHATTYPENEARBYASSISTANT = 107  # 附近助手
    KCHATTYPENEARBYINTERACT = 108  # 附近互动
    KCHATTYPEMATCHFRIENDFOLDER = 109  # 匹配好友文件夹
    KCHATTYPENEARBYFOLDER = 110  # 附近文件夹
    KCHATTYPETEMPADDRESSBOOK = 111  # 临时通讯录
    KCHATTYPENEARBYHELLOFOLDER = 112  # 附近打招呼文件夹
    KCHATTYPECIRCLE = 113  # 圈子
    KCHATTYPESQUAREPUBLIC = 115  # 广场公开
    KCHATTYPEGAMEMESSAGEFOLDER = 116  # 游戏消息文件夹
    KCHATTYPETEMPWPA = 117  # 临时 WPA
    KCHATTYPESERVICEASSISTANT = 118  # 服务助手
    KCHATTYPETEMPNEARBYPRO = 119  # 临时附近 Pro
    KCHATTYPERELATEACCOUNT = 131  # 关联账号
    KCHATTYPEQQNOTIFY = 132  # QQ 通知
    KCHATTYPEGROUPBLESS = 133  # 群祝福
    KCHATTYPEDATALINEMQQ = 134  # 数据线 MQQ
    KCHATTYPESERVICEASSISTANTSUB = 201  # 服务助手子类


#### NTGrayTipElementSubTypeV2 - 系统灰条子类型
class NTGrayTipElementSubTypeV2(IntEnum):
    GRAYTIP_ELEMENT_SUBTYPE_UNKNOWN = 0  # 未知
    GRAYTIP_ELEMENT_SUBTYPE_REVOKE = 1  # 撤回消息
    GRAYTIP_ELEMENT_SUBTYPE_PROCLAMATION = 2  # 公告
    GRAYTIP_ELEMENT_SUBTYPE_EMOJIREPLY = 3  # 表情回复
    GRAYTIP_ELEMENT_SUBTYPE_GROUP = 4  # 群相关
    GRAYTIP_ELEMENT_SUBTYPE_BUDDY = 5  # 好友相关
    GRAYTIP_ELEMENT_SUBTYPE_FEED = 6  # 动态
    GRAYTIP_ELEMENT_SUBTYPE_ESSENCE = 7  # 精华消息
    GRAYTIP_ELEMENT_SUBTYPE_GROUPNOTIFY = 8  # 群通知
    GRAYTIP_ELEMENT_SUBTYPE_BUDDYNOTIFY = 9  # 好友通知
    GRAYTIP_ELEMENT_SUBTYPE_FILE = 10  # 文件相关
    GRAYTIP_ELEMENT_SUBTYPE_FEEDCHANNELMSG = 11  # 动态频道消息
    GRAYTIP_ELEMENT_SUBTYPE_XMLMSG = 12  # XML 消息
    GRAYTIP_ELEMENT_SUBTYPE_LOCALMSG = 13  # 本地消息
    GRAYTIP_ELEMENT_SUBTYPE_BLOCK = 14  # 屏蔽
    GRAYTIP_ELEMENT_SUBTYPE_AIOOP = 15  # AIO 操作
    GRAYTIP_ELEMENT_SUBTYPE_WALLET = 16  # 钱包
    GRAYTIP_ELEMENT_SUBTYPE_JSON = 17  # JSON


##### PokeType - 戳一戳
class PokeType(IntEnum):
    POKE_TYPE_POKE_OLD = 0  # 旧版戳一戳
    POKE_TYPE_POKE = 1  # 戳一戳
    POKE_TYPE_GIVING_HEART = 2  # 比心
    POKE_TYPE_APPROVE = 3  # 点赞
    POKE_TYPE_HEART_BREAK = 4  # 心碎
    POKE_TYPE_HI_TOGETHER = 5  # 一起嗨
    POKE_TYPE_GREAT_MOVE = 6  # 精彩操作
    POKE_TYPE_VAS_POKE = 126  # VAS 戳一戳


###### FaceType - 表情种类
class FaceType(IntEnum):
    Unknown = 0  # 未知
    OldFace = 1  # 老表情
    Normal = 2  # 常规表情
    AniSticke = 3  # 动画贴纸
    Lottie = 4  # 新格式表情
    Poke = 5  # 可变 Poke


####### PicType - 图片格式
class PicType(IntEnum):
    NEWPIC_JPEG = 1000  # JPEG
    NEWPIC_PNG = 1001  # PNG
    NEWPIC_WEBP = 1002  # WebP
    NEWPIC_PROGERSSIV_JPEG = 1003  # 渐进式 JPEG
    NEWPIC_SHARPP = 1004  # SHARPP
    NEWPIC_BMP = 1005  # BMP
    NEWPIC_GIF = 2000  # GIF
    NEWPIC_APNG = 2001  # APNG


######## NTVideoType - 视频格式
class NTVideoType(IntEnum):
    VIDEO_FORMAT_AVI = 1  # AVI
    VIDEO_FORMAT_MP4 = 2  # MP4
    VIDEO_FORMAT_WMV = 3  # WMV
    VIDEO_FORMAT_MKV = 4  # MKV
    VIDEO_FORMAT_RMVB = 5  # RMVB
    VIDEO_FORMAT_RM = 6  # RM
    VIDEO_FORMAT_AFS = 7  # AFS
    VIDEO_FORMAT_MOV = 8  # MOV
    VIDEO_FORMAT_MOD = 9  # MOD
    VIDEO_FORMAT_TS = 10  # TS
    VIDEO_FORMAT_MTS = 11  # MTS


######### SendStatusType - 发送状态
class SendStatusType(IntEnum):
    KSEND_STATUS_FAILED = 0  # 发送失败
    KSEND_STATUS_SENDING = 1  # 发送中
    KSEND_STATUS_SUCCESS = 2  # 发送成功
    KSEND_STATUS_SUCCESS_NOSEQ = 3  # 发送成功（无序列）


########## TipGroupElementType - 群提示类型
class TipGroupElementType(IntEnum):
    KUNKNOWN = 0  # 未知
    KMEMBERADD = 1  # 成员加入
    KDISBANDED = 2  # 群解散
    KQUITTE = 3  # 退出群
    KCREATED = 4  # 群创建
    KGROUPNAMEMODIFIED = 5  # 群名修改
    KBLOCK = 6  # 屏蔽
    KUNBLOCK = 7  # 取消屏蔽
    KSHUTUP = 8  # 禁言
    KBERECYCLED = 9  # 被回收
    KDISBANDORBERECYCLED = 10  # 解散或被回收


__all__ = [
    "NTMsgType",
    "ElementType",
    "ChatType",
    "NTGrayTipElementSubTypeV2",
    "PokeType",
    "FaceType",
    "PicType",
    "NTVideoType",
    "SendStatusType",
    "TipGroupElementType",
]
