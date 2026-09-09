---
title: QXlnt 实现Excel读取Demo 
date: 2023-04-25
permalink: /2023/04/25/qxlnt-excel-reading/
tags: 
- Qt
- Qxlnt
- xlnt
categories:
- 学习
---

> 介绍：

QXlnt 是一个基于xlnt库的帮助程序项目，允许在Qt中使用xlnt。

xlnt库时一个现代C++库，用于操作内存中的电子表格并从xlsx文件中读取/写入 。

<!-- more -->

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230426095449354.png" alt="image-20230426095449354" style="zoom:50%;" />

## 1 导入Qxlnt  xlnt两个文件夹

- 从官网下载Qxlnt 库使用  [QtExcel/Qxlnt](https://github.com/QtExcel/Qxlnt)
- 复制Qxlnt ，xlnt两个文件夹到自己项目中

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230426095430324.png" alt="image-20230426095430324" style="zoom:50%;" />

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230426095407177.png" alt="image-20230426095407177" style="zoom:50%;" />

## 2 在项目.pro 文件中加入

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230426095339912.png" alt="image-20230426095339912" style="zoom:50%;" />

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230426095318604.png" alt="image-20230426095318604" style="zoom:50%;" />

## 3 替换

进入Qxlnt ，打开Qxlnt.pri

将 `../xlnt/` 全部替换成 `$$PWD/../xlnt/`

![image-20230426095251986](https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230426095251986.png)



## 4 验证

去官网复制个例子运行

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230426095228089.png" alt="image-20230426095228089" style="zoom:50%;" />



<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230426095204323.png" alt="image-20230426095204323" style="zoom:50%;" />



## 5 成功写入

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230426095135990.png" alt="image-20230426095135990" style="zoom:50%;" />



> 引用

[ xlnt 参考文档](https://tfussell.gitbooks.io/xlnt/content/)

[QT-XLSX,Excel快速读写经验 | 码农家园 (codenong.com)](https://www.codenong.com/cs105374779/)



------

源码 地址：

https://github.com/silent426/QtLearning.git
