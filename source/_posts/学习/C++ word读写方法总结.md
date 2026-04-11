---
title: C++ 实现word读写
tags: 
- DuckX
- minidocx
- Python-docx 
categories:
- 学习
---

[C++(Qt) 和 Word、Excel、PDF 交互总结 - kevinlq - 博客园 (cnblogs.com)](https://www.cnblogs.com/kevinlq/p/16006334.html)

<!-- more -->

## 1. XML 模板替换 标签替换

> 事先编辑好一份 `Word` 模板，需要替换内容的
> 地方预留好位置，然后使用特殊字段进行标记，后面使用代码进行全量替换即可完成

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230523102123986.png" alt="image-20230523102123986" style="zoom:50%;" />


    strAllContent.replace("$VALUE0", "1");
    strAllContent.replace("$VALUE1", QString::fromLocal8Bit("法外狂徒张三"));
    strAllContent.replace("$VALUE2", QString::fromLocal8Bit("考试不合格"));
    strAllContent.replace("$VALUE3", "2");
    strAllContent.replace("$VALUE4", QString::fromLocal8Bit("李四"));
    strAllContent.replace("$VALUE5", QString::fromLocal8Bit("合格"));
    
    ...

## 2. COM组件方式

> 原理：采用 `Micro Soft`公开的接口进行通讯，进行读写时会打开一个 Word 进程来交互

Microsoft 组件对象模型（COM）定义了一个二进制互操作性标准，用于创建在运行时交互的可重用软件库。

`Qt` 为我们提供了专门进行交互的类和接口，使用 `Qt ActiveX`框架就可以很好的完成交互工作

上手简单，但是写入导出较慢



## 3. HTML方式

> 原理：这种方式得益于 `Word`支持 HTML格式导出渲染显示，那么反向也可以支持，需要我们拼接 `HTML`格式内容，然后写入文件保存成 `.doc`格式



- 插入的图片是本地图片文件的链接，导出的 word文档拷贝到其它电脑图片无法显示

优点：跨平台，不仅限于 Windows平台，代码可扩展性比较好
导出速度快、代码可扩展；
缺点：字符串拼接 HTML 容易出错，缺失标签导出后无法显示；
插入的图片是本地图片文件的链接，导出的 word文档拷贝到其它电脑图片无法显示



## 4. 第三方库

### 开源库

 **DuckX**
https://github.com/amiremohamadi/DuckX
缺文档，缺例子，复杂 没发现插入图片的方法

**DocxFactory**

https://github.com/DocxFactory/DocxFactory
缺例子文档，时间太久, 官方文档已经打不开

**minidocx**

https://github.com/totravel/minidocx
轻量化，项目比较完整，说明比较详细，但是不能插入图片

TO DO 可以尝试扩展



### 商业类库 

**aspose.words**
https://products.aspose.com/words/zh/cpp/edit/docx/
免费的导出的文档有水印，付费使用





## 5. 使用python库间接实现

曲线救国：
 调用Python-docx库
https://zhuanlan.zhihu.com/p/564081044

https://github.com/kevinlq/QtPythonDocx#%E5%85%B3%E4%BA%8E%E4%BD%9C%E8%80%85
有文档，有教程，有可运行的项目

需要配置对用python 环境

