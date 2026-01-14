---
title: TYDH_LightDemo 光源控制器 Demo：实现方式说明
date: 2026-01-14
tags: 
- C#
- 机器视觉
- 光源控制器
categories:
- [工作日志, 从零搭建视觉系统]
---

> 适用范围：本工程为 WPF（.NET Framework 4.8）简易 Demo，用于通过串口控制 TYDH 系列光源控制器。

本文用**通俗易懂**的方式说明：这个 Demo 是如何组织代码、如何配置串口、如何按协议发送命令来控制亮度的。

<!--more-->

[Demo地址](https://github.com/conf-haolee/Vision-Next/tree/main/Light/TYDH_LightDemo)

## 1. Demo 能做什么

- 枚举本机串口（COM 口），选择端口后打开/关闭。
- 支持两种协议发送方式：
  - **short（短指令）**：按通道逐条发送，每个通道一条命令。
  - **long（长指令）**：把所有通道拼成一条命令，一次性发送。
- 支持 4 通道亮度输入（0~255），点击 **Send** 发送。

---

## 2. 工程结构与关键类

本 Demo 的核心文件只有三个：

- `Models/LightParameters.cs`
  - 存放“串口参数 + 光源参数”（例如 PortName、BaudRate、OrderType、ChannelValues）。
- `Core/TydhLightController.cs`
  - 串口打开/关闭、发送 short/long 指令、保存/加载配置。
- `MainWindow.xaml / MainWindow.xaml.cs`
  - WPF UI：从界面读取参数，调用 `TydhLightController` 完成操作。

---

## 3. 参数对象：LightParameters 是什么

`LightParameters` 用于描述一次控制所需的所有参数，主要分两类：

### 3.1 串口通讯参数

- `PortName`：例如 `COM3`
- `BaudRate`：例如 `9600`（必须与设备一致）
- `DataBits`：通常为 `8`（**必须在 5~8**，否则 Open 会报错）

> 这些参数**只要有一个不匹配**，就可能出现“程序发送了，但设备没响应”的情况。

### 3.2 光源控制参数

- `OrderType`：`short` / `long`（决定发送协议格式）
- `ChannelNumber`：Demo 固定 4
- `ChannelValues`：亮度列表，例如 `[0, 128, 255, 0]`

通道和值采用约定：

- `ChannelValues[0]` 表示通道 1
- `ChannelValues[1]` 表示通道 2
- …以此类推

---

## 4. 串口生命周期：Open / Send / Close

所有串口操作都封装在 `TydhLightController` 内。

### 4.1 打开串口（Open）

`Open()` 做的事情（简化描述）：

1. 检查 `PortName` 是否为空
2. 如果串口已经打开，先 `Close()` 一次（避免占用与状态不一致）
3. 设置串口参数：
   - `PortName / BaudRate / DataBits`
   - `StopBits = One`
   - `Parity = None`
   - `Encoding = ASCII`（协议是 ASCII 文本）
4. 调用 `_serialPort.Open()`

常见错误：

- **DataBits 非法**：设置为 0/9 会抛异常：`参数必须介于 5 和 8 之间`
- **串口被占用**：其它程序占用了同一 COM 口
- **波特率不一致**：能打开但设备不响应

### 4.2 发送亮度（Send）

调用 `SetValues(values)`：

- 先检查串口必须已打开
- 根据 `OrderType` 选择：
  - `SendShort(values)` 或 `SendLong(values)`

### 4.3 关闭串口（Close）

`Close()` 的逻辑比较“安全”：

1. 如果串口已打开：
2. 先把所有通道发送为 0（关灯）
3. 再真正 `_serialPort.Close()`

这样做的好处：

- 防止程序退出后光源仍保持亮度

---

## 5. 协议实现：short 与 long 两种指令有什么区别

> 本 Demo 的 long 指令格式对应参考工程 **VX_TYDH_F** 的实现方式。

### 5.1 short（短指令）——逐通道发送

特点：

- 每个通道一条命令
- 每条命令包含校验位（BCC）
- 通道数越多，发送次数越多

基本拼接规则：

- 起始符：`S`
- 命令字：`4`
- 通道号：`1/2/3/4...`
- 值：把亮度从十进制转为十六进制（大写），并补齐 3 位
  - 例：`255 -> 0FF`
- 校验：对“前面这段字符串”做 XOR（BCC）

伪代码：

- `data = "S" + "4" + channel + valueHex3`
- `bcc = BCC(data)`
- `write(data + bcc)`

### 5.2 long（长指令）——一次性发送所有通道（重点）

长指令的优势：

- 把所有通道一次性发出去
- 通道间亮度更新更“同步”

本 Demo long 格式（对齐 VX_TYDH_F）：

- 起始符：`S`
- 指令体：每个通道用 **3 位十进制**，并以 `T` 结尾
- 结束符：`C#`

例如 4 通道：

- values = `[0, 128, 255, 0]`
- body = `000T128T255T000T`
- 最终写入：`S000T128T255T000TC#`

> 注意：长指令一般**不需要 BCC**（本设备协议如此）。如果你遇到设备不响应，需要回查硬件协议文档确认。

---

## 6. BCC（异或校验）是怎么计算的

短指令用的 `BCC` 属于经典 XOR 校验：

1. 把字符串按某种编码转字节（Demo 对齐参考工程，使用 `Encoding.Default`）
2. 对所有字节做异或：`temp ^= bytes[i]`
3. 输出 `temp` 的十六进制字符串

如果遇到“短指令不响应，但长指令正常”，可能需要确认：

- 设备是否要求校验位固定两位（例如 `0A` 而不是 `A`）
- 通道号是否要求两位（例如 `01/02`）

---

## 7. UI（MainWindow）是如何驱动控制器的

WPF 端为了简单，直接在 `MainWindow.xaml.cs` 里做三件事：

1. 启动时枚举串口列表 `SerialPort.GetPortNames()`
2. 点击 **Open**：
   - `ReadUiParameters()` 读取界面参数
   - `controller.ApplyParameters(p)`
   - `controller.Open()`
3. 点击 **Send**：
   - 读取 `ChannelValues`
   - `controller.SetValues(values)`
4. 点击 **Close**/窗口关闭：
   - `Close()` / `Dispose()`

---

## 8. 常见问题排查（快速）

### 8.1 Open 失败提示 DataBits 范围错误

- 原因：`DataBits` 被设置成了 0/9 等非法值
- 解决：保证 `DataBits` 在 5~8，通常用 8

### 8.2 能 Open，但 Send 无效果

优先检查：

1. **波特率是否与设备一致**（VX 工具可控通常是 9600）
2. `OrderType` 是否选对（你测试的是 long 还是 short）
3. long 指令是否按 `S + 000T... + C#` 发送

---

## 9. 后续可扩展方向

- 增加通道数可配置（UI 增加通道输入，或动态生成控件）
- 对 `ChannelValues` 做范围校验与限幅（0~255）
- 做成 MVVM：实现 `INotifyPropertyChanged`，实现 IsOpen 状态自动刷新
- 增加串口接收（如设备返回状态/ACK）并做日志显示

---

## 10. 总结

本 Demo 的思路很简单：

- **UI 负责采集参数**
- **控制器类负责封装串口与协议**
- **long 指令对齐 VX_TYDH_F**：一次性拼接并发送 `S + 000T... + C#`

如果你需要将 Demo 演进成可复用的库（比如提供接口、日志、异常码、自动重连等），建议在此基础上再做一层抽象（例如加入 ViewModel/Service 层）。



> ## 扩展

很多品牌的光源控制器底层都是走串口通讯（RS-232/RS-485/虚拟串口 USB CDC 等），差别主要在“上层协议/指令集”和一些工程化细节上，而不是“串口本身”。
具体差异通常体现在这些方面：

1. 指令协议/命令集不同
   •	帧头/帧尾（例如你这个是 S ... C#）
   •	通道编号规则、是否要补零、ASCII 还是二进制
   •	亮度值范围与编码（十进制、十六进制、BCD、0~255/0~1023 等）
   •	是否需要校验（BCC/LRC/CRC）、校验位长度与大小写
   •	单通道指令 vs 多通道一帧指令（short/long 类似区别）

2. 串口参数默认值不同
   •	波特率、数据位、校验位、停止位（虽常见是 9600/8/N/1，但并非都一样）

3. 设备行为差异（很重要）
   •	是否有 ACK/返回码、错误码
   •	是否需要节流（发送间隔），连续发送会不会丢包
   •	是否支持查询当前亮度/温度/报警状态等

   **所以从软件实现角度：串口打开/写入/读取这套代码框架基本通用，主要需要“适配”的是每家协议（你工程里主要就是 SendLong/SendShort/Bcc 这类部分）。如果后续要支持多品牌，通常做法是抽象一个接口（例如 ILightProtocol），把“串口传输层”和“协议编码层”分开。**
