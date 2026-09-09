---
title: 机器视觉产线仿真的一些思考：Vision Line Simulator 与虚拟调试
date: 2026-08-26
permalink: /2026/08/26/vision-line-simulator/
tags:
- 机器视觉
- 仿真
- Virtual Commissioning
- 数字孪生
categories:
- [工作, 机器视觉]
---

<div align="center">
<img src=https://raw.githubusercontent.com/conf-haolee/Images/master/PicGoImgVisionLineSimulator.png  width=400px />
</div>

> 对于机器视觉项目来说，产线仿真的核心不一定是把真实物料、相机和光学环境全部通过3D重新生成，而是建立一套可以模拟 **产品流转、PLC状态、相机触发、真实图片采集、视觉检测、OK/NG结果反馈、复判、分拣以及MES数据上传** 的虚拟产线。
>
> 如果能够在设备真正完成之前，让视觉软件提前运行在这样的虚拟环境中，那么很多原本只能到现场才能发现的问题，就可以提前在办公室完成验证。

<!--more-->

在工业机器视觉项目中，经常会遇到一个比较现实的问题：

> 视觉软件虽然已经开发完成，但真正能够完整调试，往往必须等待机台、PLC、相机、光源、MES以及其他工位全部准备完成。

于是一个项目经常会出现这样的开发过程：

```text
视觉算法开发
    ↓
视觉软件开发
    ↓
等待机台
    ↓
等待PLC
    ↓
现场安装
    ↓
相机接入
    ↓
开始第一次完整联调
    ↓
发现通讯、节拍、状态机、异常处理等问题
```

很多问题其实并不属于视觉算法本身。

例如：

- PLC Trigger 时序不正确
- Vision Busy 没有正确复位
- 相机重复触发
- 图像漏采
- 算法超时
- 多工位产品ID对应错误
- NG信息传递错误
- 复判结果没有正确覆盖原检测结果
- 分拣工位拿错产品结果
- MES上传数据不完整
- 某个工位掉线后整线状态异常

这些问题通常只有整条设备真正跑起来以后才会暴露。

因此最近产生了一个想法：

```text
能不能给机器视觉项目搭建一条“虚拟产线”？
```

让视觉程序在没有真实设备的情况下，也能够完成接近现场的完整运行。

这就是本文想讨论的：

**Vision Line Simulator——机器视觉产线仿真与虚拟调试平台。**

---

## 一、机器视觉产线是否可以进行仿真

答案是：

```text
完全可以
```

而且不一定需要一开始就建立非常复杂的3D模型。

例如一条典型AVI视觉检测线，可以抽象成：

```text
料盘进入
   ↓
产品到达检测位置
   ↓
到位Sensor触发
   ↓
PLC控制相机拍照
   ↓
Camera Trigger
   ↓
视觉软件获得图片
   ↓
HALCON / AI算法检测
   ↓
OK / NG / Error
   ↓
结果发送PLC
   ↓
PLC控制机台动作
   ↓
下一产品进入
```

如果把其中的真实硬件替换：

```text
真实PLC
    ↓
Virtual PLC

真实Camera
    ↓
Virtual Camera

真实Sensor
    ↓
Virtual IO

真实产品
    ↓
Virtual Product
```

视觉软件本身则尽量保持不变。

最终就可以形成：

```text
Virtual Machine
      ↓
Virtual PLC
      ↓
Virtual Camera
      ↓
Real Vision Software
      ↓
OK / NG
      ↓
Virtual PLC
      ↓
Virtual Machine Action
```

这已经是一条完整的机器视觉虚拟检测线。

---

## 二、不需要把真实物料完全仿真出来

最开始考虑这个问题时，很容易想到：

```text
Blender
Unity
3D CAD
光学仿真
镜头模型
光源模型
材质
真实反射
```

然后生成一张完全仿真的工业图像。

这种方式当然是可以实现的。

例如：

```text
3D Product
   +
Defect
   +
Light
   +
Camera
   +
Lens
        ↓
Render
        ↓
Synthetic Image
        ↓
Vision Algorithm
```

但是对于机器视觉项目虚拟调试来说，我认为第一阶段并没有必要做到这么复杂。

因为真实项目中往往已经积累了大量：

- OK图片
- NG图片
- 不同缺陷图片
- 不同工位图片
- 不同曝光图片
- 不同产品型号图片

那么完全可以：

```text
虚拟产品
      ↓
到达虚拟Camera
      ↓
Camera Trigger
      ↓
从真实Dataset中读取图片
      ↓
发送给视觉软件
```

也就是说：

> **机械流程是虚拟的，但视觉软件处理的图像可以是真实现场图片。**

例如：

```text
Tray_0001
│
├─ Product_001
│   ├─ Back.bmp
│   ├─ Front.bmp
│   └─ Special.bmp
│
├─ Product_002
│   ├─ Back.bmp
│   ├─ Front.bmp
│   └─ Special.bmp
│
└─ Product_003
```

当虚拟产品 `Product_001` 到达反面检查工位时：

```text
Virtual Camera
      ↓
读取
Product_001/Back.bmp
      ↓
视觉软件
```

到达正面工位：

```text
读取
Product_001/Front.bmp
```

这样既保持了真实视觉检测效果，又省去了大量复杂的物理光学仿真工作。

---

## 三、Vision Line Simulator真正需要模拟什么

如果不重点模拟真实光学，那么平台真正需要模拟的东西是什么？

我认为主要可以分成下面几个部分。

| 模块 | 主要作用 |
|---|---|
| Virtual Product | 模拟产品和产品ID |
| Virtual Tray | 模拟料盘以及产品布局 |
| Virtual Station | 模拟不同检测工位 |
| Virtual Sensor | 模拟到位、离位等传感器 |
| Virtual PLC | 模拟PLC状态机以及IO |
| Virtual Camera | 模拟相机Trigger和图像返回 |
| Vision Connector | 连接真实视觉软件 |
| Virtual MES | 模拟MES接收、查询、上传 |
| Review Station | 模拟人工复判 |
| Sorting Station | 根据最终结果执行分拣 |
| Event System | 管理整条产线的事件和时间 |
| Dataset | 保存真实检测图片和标准结果 |

这里真正的核心并不是3D界面，而是：

```text
Product
   +
Station
   +
State
   +
Signal
   +
Event
```

也就是整条产线的**逻辑状态**。

---

## 四、一条真正的视觉产线往往由很多主机构成

实际项目通常不会只有一个视觉工位。

例如一条比较完整的AVI检测线，可能包括：

```text
反面检查
   ↓
正面检查
   ↓
部位专检
   ↓
复判工位
   ↓
分拣工位
   ↓
MES数据机台
```

如果简单理解为：

```text
一台电脑模拟一整条产线
```

软件很容易变得非常复杂。

特别是如果每一个工位都直接打开一个完整视觉软件：

```text
反面视觉软件
正面视觉软件
专检视觉软件
复判软件
分拣软件
MES软件
```

那么一台电脑上同时运行大量窗口，很快就会变得混乱。

因此更合理的思想应该是：

```text
不要模拟“电脑”

而是模拟“Station”
```

也就是：

**工位才是虚拟产线的基本单位。**

---

## 五、将每一台设备抽象成 Station

例如：

```text
Station
│
├─ StationId
├─ StationType
├─ PreviousStation
├─ NextStation
│
├─ StateMachine
├─ VirtualIO
├─ VirtualPLC
├─ VirtualCamera
│
├─ VisionConnector
├─ InputBuffer
├─ OutputBuffer
│
└─ Result
```

那么反面检测：

```text
StationType = Vision
StationId   = BackInspection
```

正面检测：

```text
StationType = Vision
StationId   = FrontInspection
```

复判：

```text
StationType = Review
```

分拣：

```text
StationType = Sorting
```

MES：

```text
StationType = MES
```

整个项目就可以由一份配置文件描述：

```json
{
  "LineName": "AVI_Line_01",

  "Stations": [
    {
      "Id": "Back",
      "Type": "Vision"
    },
    {
      "Id": "Front",
      "Type": "Vision"
    },
    {
      "Id": "Special",
      "Type": "Vision"
    },
    {
      "Id": "Review",
      "Type": "Review"
    },
    {
      "Id": "Sort",
      "Type": "Sorting"
    },
    {
      "Id": "MES",
      "Type": "MES"
    }
  ]
}
```

以后换一个项目，本质上只是：

```text
LineConfig.json
```

发生变化。

仿真平台本身不需要重新开发。

---

## 六、多工位如何在一台电脑上运行

比较适合第一阶段的方式是：

```text
一个Station = 一个独立节点
```

例如开发一个统一程序：

```text
StationHost.exe
```

然后通过不同配置运行多个实例：

```text
StationHost.exe Back.json

StationHost.exe Front.json

StationHost.exe Special.json

StationHost.exe Review.json

StationHost.exe Sort.json

StationHost.exe MES.json
```

逻辑上它们相当于现场的多台独立主机。

但是实际上可以全部运行：

```text
127.0.0.1
```

只使用不同Port：

```text
Back        8101
Front       8102
Special     8103
Review      8104
Sorting     8105
MES         8106
```

于是：

```text
一台开发电脑
       ↓
虚拟出了一个完整的设备局域网
```

将来如果性能不足，也可以把Station分布到：

```text
PC01
PC02
PC03
```

因为Station之间本来就是通过网络协议通信，所以架构不需要发生大的变化。

这比一开始就采用复杂虚拟机或者容器方案更加适合工业视觉软件。

---

## 七、增加一个 Line Simulation Hub

如果所有Station都是独立节点，那么还需要一个角色负责管理整个世界。

可以把它称为：

```text
Line Simulation Hub
```

或者：

```text
Simulation Engine
```

它负责：

```text
创建Tray
创建Product

管理Product ID

控制产品流转

维护Station状态

产生Sensor信号

管理Simulation Time

记录事件

注入异常

统计Cycle Time
```

例如：

```text
Product = PCS001
```

在Hub里面可能保存：

```text
ProductID = PCS001

CurrentStation = Front

BackResult = OK

FrontResult = NG

SpecialResult = None

ReviewResult = None

FinalResult = None
```

当反面检测完成以后：

```text
Back Station
     ↓
Inspection Result
     ↓
Simulation Hub
     ↓
Product Moving
     ↓
Front Station
```

这里真正移动的其实不是2600万像素的大图片。

而只是：

```text
ProductID
StationID
Result
Timestamp
```

具体图像由对应Station内部的Virtual Camera读取。

这样系统会轻很多。

---

## 八、Virtual Camera：视觉仿真的关键模块

对于视觉软件来说，一个非常关键的问题就是：

```text
如何让真实视觉程序认为自己连接了一台Camera？
```

可以设计统一接口：

```csharp
public interface ICamera
{
    void Open();

    void Close();

    void Trigger();

    Image GrabImage();
}
```

生产环境：

```text
ICamera
   ↓
DahengCamera
```

仿真环境：

```text
ICamera
   ↓
VirtualCamera
```

Virtual Camera收到Trigger：

```text
Trigger
   ↓
读取当前ProductID
   ↓
查找Dataset
   ↓
加载对应图片
   ↓
返回视觉软件
```

例如：

```text
ProductID = PCS001
StationID = Front

      ↓

Dataset/
Tray001/
PCS001/
Front.bmp
```

从视觉算法的角度看：

```text
GrabImage()
```

仍然返回一张正常图片。

至于这张图片到底来源于：

```text
真实工业相机

还是

磁盘Dataset
```

视觉算法根本不需要知道。

HALCON本身的图像采集接口也采用了类似的统一接口思想：通过统一的图像采集接口连接大量实际相机和采集设备，从而把具体硬件实现与上层视觉处理尽量隔离。

这种设计方式对于Virtual Camera非常值得参考。

---

## 九、Virtual PLC同样应该进行接口抽象

Camera如此，PLC也是如此。

例如：

```csharp
public interface IPlcClient
{
    bool ReadBit(string address);

    void WriteBit(string address, bool value);

    int ReadInt(string address);

    void WriteInt(string address, int value);
}
```

生产环境：

```text
SiemensPLC
OmronPLC
MitsubishiPLC
```

仿真环境：

```text
VirtualPLC
```

视觉软件原来：

```text
CameraReady
Trigger
VisionBusy
VisionOK
VisionNG
```

在虚拟环境中仍然保持相同逻辑：

```text
VirtualPLC
      ↓
Trigger = ON

Vision
      ↓
Busy = ON

检测完成
      ↓
OK = ON
Busy = OFF
```

这样就可以在没有真实PLC的情况下测试完整握手逻辑。

---

## 十、整个视觉检测流程就可以真正跑起来

例如一个Product：

```text
PCS001
```

进入产线。

### 1. 反面检查

```text
PCS001
   ↓
Back Station
   ↓
Sensor ON
   ↓
Camera Trigger
   ↓
VirtualCamera
   ↓
Back.bmp
   ↓
真实视觉软件
   ↓
Result = OK
```

### 2. 正面检查

```text
PCS001
   ↓
Front Station
   ↓
Front.bmp
   ↓
Vision
   ↓
Result = NG
```

检测：

```text
Defect = FPC脏污
```

### 3. 部位专检

```text
Special.bmp
   ↓
Vision
   ↓
Result = OK
```

此时产品数据：

```text
Back    = OK
Front   = NG
Special = OK
```

### 4. 复判工位

复判软件获得：

```text
ProductID

Front NG Image

Defect Type
```

经过人工或者自动复判：

```text
ReviewResult = NG
```

### 5. 分拣工位

获得最终结果：

```text
FinalResult = NG
```

执行：

```text
NG Bin
```

### 6. MES

最终上传：

```text
ProductID

BackResult

FrontResult

SpecialResult

ReviewResult

FinalResult

CycleTime

DefectInfo
```

到这里，实际上已经完成了一条完整视觉产线的虚拟运行。

---

## 十一、真实图片不仅可以用于仿真，还可以变成自动回归测试集

这个方向继续思考下去，会发现Dataset的价值不仅仅是：

```text
代替Camera
```

还可以给每一片产品增加一个标准答案：

```json
{
  "ProductId": "PCS001",

  "ExpectedResult": "NG",

  "Defects": [
    "FPC脏污"
  ]
}
```

那么视觉软件运行以后可以自动比较：

```text
Expected Result
       VS
Vision Result
```

例如测试1000片历史产品：

```text
1000 PCS
   ↓
Vision Line Simulator
   ↓
自动运行
```

最终统计：

```text
TP
FP
FN
TN

Precision
Recall

平均检测时间
最大检测时间
P95检测时间

通信异常次数
Trigger异常次数
算法超时次数
```

这时候Vision Line Simulator又多了另外一个能力：

```text
Vision Regression Test
```

也就是：

**视觉软件自动回归测试。**

当算法或者软件版本更新以后：

```text
Version 1.20
     VS
Version 1.21
```

都可以重新跑一次历史Dataset。

这比人工打开几百张图片测试效率高很多。

---

## 十二、还可以加入 Fault Injection

虚拟环境有一个真实设备很难做到的优势：

```text
可以故意让系统出错
```

例如增加：

```text
Fault Injection
```

模拟：

- Camera超时
- Camera断线
- PLC通信断开
- Trigger重复
- Trigger丢失
- Image丢失
- Algorithm Timeout
- Vision Busy不复位
- MES断线
- MES响应超时
- 连续NG
- Product ID错误
- 工位掉线
- 复判超时

例如：

```text
正常流程：

Trigger
   ↓
Image
   ↓
Result
```

故障测试：

```text
Trigger
   ↓
Camera Timeout
   ↓
???
```

此时就可以观察：

```text
视觉软件有没有报警？

PLC有没有停止？

能不能Retry？

产品状态有没有丢失？

MES记录有没有异常？
```

这其实比单纯验证视觉算法更加接近真正的设备软件测试。

---

## 十三、最终可以测试整线Cycle Time

有了完整Event System以后，还可以记录：

```text
08:00:00.000 ProductArrived

08:00:00.020 SensorON

08:00:00.050 CameraTrigger

08:00:00.080 ImageAcquired

08:00:00.215 VisionResult

08:00:00.230 PLCReceived

08:00:00.260 ConveyorStart
```

那么就可以分析：

```text
Camera CT

Vision CT

PLC Response

Station CT

Line CT
```

甚至测试：

```text
Speed = 1X
Speed = 2X
Speed = 5X
Speed = MAX
```

在不考虑真实机械惯性的情况下，让软件以最大速度运行。

这样很容易发现：

```text
高频Trigger下有没有Race Condition？

线程有没有堵塞？

Queue会不会堆积？

图片保存速度是否跟得上？

MES上传会不会成为瓶颈？
```

---

## 十四、市面上已经有类似的Virtual Commissioning思想

这个想法并不是完全没有工业产品可以参考。

目前工业自动化领域已经存在比较成熟的：

```text
Virtual Commissioning
```

也就是：

**虚拟调试。**

典型产品包括：

| 产品 | 主要方向 |
|---|---|
| Visual Components | 制造产线3D仿真 / Virtual Commissioning |
| Rockwell Emulate3D | 自动化设备和物流产线仿真 |
| Siemens SIMIT | 设备、传感器、执行器和控制系统仿真 |
| Siemens PLCSIM Advanced | Siemens虚拟PLC |
| HALCON Image Acquisition Interface | 视觉采集接口抽象 |

这些平台证明了一件事：

```text
在真实设备完成以前测试控制软件
```

本身已经是一个成熟的工业方向。

但是目前这些平台普遍更加关注：

```text
机械
PLC
Robot
Conveyor
Sensor
Drive
```

而机器视觉往往只是其中一个设备节点。

---

## 十五、Vision Line Simulator可以更加偏向Vision

这也是我认为这个想法比较有意思的地方。

传统工业仿真平台更像：

```text
PLC           ★★★★★

机械          ★★★★★

机器人        ★★★★★

输送线        ★★★★★

Vision        ★★
```

而Vision Line Simulator可以反过来：

```text
Vision Software        ★★★★★

Image Dataset          ★★★★★

Virtual Camera         ★★★★★

PLC                    ★★★★

MES                    ★★★★

Review                 ★★★★

Sorting                ★★★★

Mechanical             ★★★

3D                     ★★
```

目标不是取代专业工业仿真软件。

而是解决机器视觉工程师最直接的问题：

```text
没有现场设备的时候

能不能把视觉项目提前跑起来？
```

---

## 十六、第一阶段其实不应该先做3D

最容易走偏的地方就是：

```text
先打开Unity

或者

先打开Blender

然后开始建一台漂亮的AVI机台
```

这个Demo可能很好看。

但是它没有解决真正的问题。

我认为平台的正确关系应该是：

```text
               Simulation Core

                      │
        ┌─────────────┼─────────────┐
        │             │             │
       WPF           3D            Web
        │             │             │
       UI          Unity         Browser
```

也就是说：

```text
Simulation Core
```

才是核心。

它管理：

```text
Time
Event
Product
Station
Signal
State
```

UI只是这个世界的一种表现方式。

第一阶段甚至可以使用非常简单的二维界面：

```text
------------------------------------------------

Tray

 ↓

[反面] → [正面] → [专检] → [复判] → [分拣] → [MES]

 ●RUN      ●RUN     ●RUN      ●RUN      ●RUN      ●RUN

------------------------------------------------

Current Product：

PCS001

Current Station：

Front

Back Result：

OK

Front Result：

NG

Cycle Time：

1.82 s

------------------------------------------------
```

这已经足够完成大量工程验证。

---

## 十七、第一阶段建议技术架构

按照目前常用的机器视觉开发环境，我认为第一阶段完全可以使用：

```text
C#
.NET
WPF

HALCON

TCP

JSON

真实Image Dataset
```

整个系统：

```text
                 Vision Line Simulator

                         │
                         ▼

                 Simulation Hub

                         │

        ┌────────────────┼────────────────┐
        │                │                │

   Back Station    Front Station    Special Station

        │                │                │
 Virtual PLC        Virtual PLC       Virtual PLC

 Virtual Camera     Virtual Camera    Virtual Camera

        │                │                │
        ▼                ▼                ▼

      Real             Real             Real
     Vision           Vision           Vision
    Software         Software         Software

        └────────────────┼────────────────┘

                         ↓

                      Review
                         ↓
                      Sorting
                         ↓
                        MES
```

第一阶段甚至不需要：

```text
Docker
Kubernetes
Unity
Blender
复杂3D物理引擎
```

先把流程真正跑起来更加重要。

---

## 十八、后续第二阶段再加入3D

当Simulation Core稳定以后，可以再增加：

```text
Unity
```

或者：

```text
Blender
```

表现：

- Conveyor
- Tray
- Product
- Camera
- Light
- Robot
- Cylinder
- Sensor
- Inspection Station

此时3D层只是监听：

```text
ProductMoved

StationStarted

CameraTriggered

ResultGenerated

CylinderActivated
```

然后播放对应动画。

最终就可以看到：

```text
Tray进入

↓

产品搬运

↓

Camera亮起

↓

视觉窗口出现真实图片

↓

NG

↓

NG分拣机构动作
```

这样3D表现和真实控制逻辑是分离的。

---

## 十九、再往后可以研究真正的光学仿真

第三阶段才可以继续研究：

```text
Camera Sensor

Lens

Light Source

Material

Reflection

Exposure

Depth of Field

Distortion
```

例如使用Blender自动生成：

```text
划伤
脏污
缺料
异物
偏位
变形
```

然后：

```text
Synthetic Image
        ↓
Vision Algorithm
```

这个方向又可以与AI训练Dataset生成结合。

于是平台会逐渐形成两个方向：

```text
                Vision Line Simulator

                  /            \

      Virtual Commissioning    Synthetic Data

              ↓                     ↓

       软件/产线验证           AI训练数据生成
```

这两个方向其实又可以互相结合。

---

## 二十、Vision Line Simulator最终可能变成什么

继续扩展以后，我认为它最终可能不仅是一个“产线动画软件”。

而是一套：

```text
机器视觉项目虚拟开发环境
```

进入一个项目：

```text
Project：AVI_Project_01
```

选择：

```text
PLC：

Simulation


Camera：

Simulation


Dataset：

2026-08-SiteDataset


MES：

Simulation


Speed：

5X
```

点击：

```text
Start Production
```

然后整个项目自动运行：

```text
Tray001进入

↓

PCS001反面检测

↓

PCS001正面检测

↓

PCS001专检

↓

PCS001复判

↓

PCS001分拣

↓

MES上传

↓

PCS002
```

最终生成：

```text
Detection Report

Communication Report

Cycle Time Report

Fault Report

Regression Report
```

这已经不仅仅是Simulator。

而更接近：

```text
Vision Virtual Commissioning Platform
```

---

## 二十一、这个方向真正想解决的问题

回到最开始的问题。

现在大量机器视觉项目开发依然是：

```text
软件先写

↓

设备完成

↓

所有人进入现场

↓

开始联调

↓

发现大量问题

↓

现场改

↓

现场测试

↓

继续改
```

而我希望未来可以逐渐变成：

```text
机械还没完成

↓

建立Virtual Line

↓

PLC开始调试

↓

Vision开始调试

↓

MES开始调试

↓

整线提前运行

↓

Fault Injection

↓

Regression Test

↓

真实设备完成

↓

Virtual → Real
```

最终现场真正需要处理的更多是：

```text
真实光学

真实机械误差

真实节拍

真实IO

真实网络环境
```

而不是到了车间以后才第一次验证：

```text
PLC到底会不会给Trigger？

VisionResult有没有正确返回？

产品ID有没有传错？

NG到底有没有进入正确的分拣工位？
```

这些问题理论上都可以提前解决。

---

## 二十二、目前对第一版的设想

第一版暂时可以叫：

```text
Vision Line Simulator V0.1
```

目标保持简单：

```text
Simulation Hub

+

Station Framework

+

Virtual PLC

+

Virtual Camera

+

真实Image Dataset

+

真实Vision Software

+

Review

+

Sorting

+

Virtual MES

+

统一Dashboard
```

先实现：

```text
一片产品
```

完整经过：

```text
反面
 ↓
正面
 ↓
专检
 ↓
复判
 ↓
分拣
 ↓
MES
```

然后扩展成：

```text
一盘产品
```

再进一步：

```text
连续多盘
```

如果这条链可以稳定运行，那么后面的：

```text
3D
Fault Injection
Cycle Test
Regression Test
Virtual PLC
真实PLC程序
```

都可以继续建立在这个基础上。

---

## 结语

机器视觉项目中的“仿真”，不一定意味着：

```text
把一个工厂完整复制到电脑里面
```

对视觉工程师来说，更有实际意义的可能是：

```text
让真实视觉软件

在没有真实产线的时候

依然能够像在现场一样运行
```

所以Vision Line Simulator最重要的并不是：

```text
3D模型有多真实
```

而是：

```text
Camera Trigger是否真实

PLC握手是否真实

Vision软件是否真实

产品流转逻辑是否真实

MES数据链路是否真实

异常场景是否真实
```

至于图像：

```text
完全可以直接使用真实现场Dataset
```

机械部分：

```text
第一阶段甚至只需要二维状态机
```

我认为这可能是一条比较适合机器视觉工程实践的Virtual Commissioning路线。

它不需要一开始就追求非常完整的数字孪生。

而是先解决一个非常具体的问题：

> **能不能在真正设备准备好以前，就让一套机器视觉项目完整地跑起来？**

如果这个问题能够解决，那么很多原本只能在现场进行的工作，就有机会被提前到办公室完成。

这可能才是机器视觉产线仿真真正值得做的地方。

------

> 参考方向

- Visual Components：Manufacturing Simulation / Virtual Commissioning
- Siemens SIMIT：自动化设备及控制系统仿真
- Siemens S7-PLCSIM Advanced：虚拟PLC
- Rockwell Automation Emulate3D：自动化设备数字孪生与Virtual Commissioning
- MVTec HALCON：Image Acquisition Interface
