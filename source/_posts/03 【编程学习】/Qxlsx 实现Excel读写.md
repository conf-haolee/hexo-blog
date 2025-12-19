---
title: Qxlsx 实现Excel读写
tags: 
- Qxlsx
- Qt
- C++ 
categories:
- 编程学习
---

**Qxlsx 是一个第三方的Excel文件读写库，使用C++ 与 Qt开发。**

<!-- more -->

## 1. 介绍

![image-20230422162532012](https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422162532012.png)

**Qxlsx 是一个第三方的Excel文件读写库，使用C++ 与 Qt开发。**

由于QtXlsx2014 年不再维护，该项目2017年起，基于Qtxlsx开发。

[GitHub库：QtExcel/QXlsx](https://github.com/QtExcel/QXlsx#qxlsx)



### 前身：Qtxlsx

两种方法开始使用Qtxlsx写一个新Excel 文件

- 方法1：使用Xlsx作为Qt5的插件模块

要使用perl

- 方法2: 直接使用源代码

window 平台尝试可以写入新Excel文件



### Qt 官网的介绍：

![image-20230422161641643](https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422161641643.png)

[Handling Microsoft Excel file format - Qt Wiki](https://wiki.qt.io/Handling_Microsoft_Excel_file_format)



## 2. 如何使用？



### 安装设置：

[How to setup QXlsx project -qmake](https://github.com/QtExcel/QXlsx#qxlsx:~:text=how%20to%20setup%20QXlsx%20project%20(qmake))

如果出错，可将其中8，9，10步骤可更改为：

1. 复制QXlsx文件夹 到项目文件根目录下：

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422163559547.png" alt="image-20230422163559547" style="zoom:50%;" />

2. 在.pro文件中添加include

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422163913732.png" alt="image-20230422163913732" style="zoom:50%;" />

构建项目后即可导入头文件

### wiki 手册：

:one: 读单元格数据

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422164839363.png" alt="image-20230422164839363" style="zoom:50%;" />

:two: 写单元格数据

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422164941230.png" alt="image-20230422164941230" style="zoom:50%;" />

...

详情：[Home · QtExcel/QXlsx Wiki (github.com)](https://github.com/QtExcel/QXlsx/wiki)



### Qxlsx 例子



应用：

#### 1 直接读取Excel

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422171345124.png" alt="image-20230422171345124" style="zoom:50%;" />

#### calendar

- Excel日历
- 创建了12个sheet表单
- 设置了单元格大小
- 修改单元格格式
- 合并单元格
- 单元格字体颜色，加粗

> [QXlsx/calendar](https://github.com/QtExcel/QXlsx/blob/master/TestExcel/calendar.cpp)

#### chart

- 饼图，三维饼图
- 柱形图，三维柱形图
- 组合图，三维折线图
- 面积图，三维面积图
- 散点图，圆环图

> [chart](https://github.com/QtExcel/QXlsx/blob/master/TestExcel/chart.cpp)

#### chartsheet

生成图与原始数据分别存在两个Excel表中

> [chartsheet](https://github.com/QtExcel/QXlsx/blob/master/TestExcel/chartsheet.cpp)

#### datavalidation

- 数据验证限制，限制单元格内数值输入的范围

> [datavalidation](https://github.com/QtExcel/QXlsx/blob/master/TestExcel/datavalidation.cpp)

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422165421867.png" alt="image-20230422165421867" style="zoom:50%;" />

#### documentpropery

- ​	设置文件的属性，创建人，公司，关键词，描述

#### extract data

导出软件Excel单元格内容在控制台显示

formula

hyperlink

image

Merge cells

numberformat



#### 2 在android上显示

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422171606819.png" alt="image-20230422171606819" style="zoom:50%;" />

#### 3 加载到网络服务器上

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422171627656.png" alt="image-20230422171627656" style="zoom:50%;" />

#### 4 显示到控制台

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422171651598.png" alt="image-20230422171651598" style="zoom:50%;" />



5 加载显示到Qt小组件上（目前未开源）

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230422172009399.png" alt="image-20230422172009399" style="zoom:50%;" />



- https://j2doll.tistory.com/654





## 3. Qxlsx存在的一些问题：

1 不支持QT4

2 不支持密码函数 ，可以使用Qxlnt补充

3 不支持Excel中的公式，可以使用Qxlnt补充⚠️（本身也能使用公式，见官网例子）

[QXlsx/formulas.cpp at master](https://github.com/QtExcel/QXlsx/blob/master/TestExcel/formulas.cpp)

4 不支持打印到打印机

5 部分支持图表，还有一些bug 尚未修复

6 只有部分功能与 QtXlsxWriter兼容

- 有关详细信息，请参阅链接。
  - https://github.com/dbzhang800/QtXlsxWriter
  - https://github.com/VSRonin/QtXlsxWriter

7 QXlsx 不支持严格格式？（非过渡模式）

- 有关详细信息，请参阅链接。https://github.com/QtExcel/QXlsx/issues/68#issuecomment-587438003

8 **Qxlsx 不提供线程安全**，在 QXlsx 库之外使用 QMutex

9 **不支持多线程和并发**。使用您自己的锁、互斥锁和信号量。



------

例子可运行源码地址：

https://github.com/silent426/QtLearning.git



