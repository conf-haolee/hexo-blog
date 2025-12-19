---
title: SSH远程连接快速上手
date: 2023-10-31 20:38:17     //发表日期
tags: 
- SSH
categories:
- 速查手册
---

`ssh user@ip`

> SSH 协议通过对网络数据进行加密和验证， 在不安全的网络环境中提供了安全的登录和其他安全网络服务。

<!-- more-->

## 01 SSH 基础知识

SSH(Secure Shell)是一种加密的网络通信协议。

**SSH 的主要作用：**

1. 远程登录
2. 数据传输
3. 密钥认证

以及隧道传输、端口转发、回话管理。

**通信模式： 服务器-客户端模式(Server-Client)**

<img src="https://raw.githubusercontent.com/conf-haolee/Images/master/uPic/5a527e3afe03bf5a8e6d0b3679505ff8.png" alt="5a527e3afe03bf5a8e6d0b3679505ff8" style="zoom:50%;" />

## 02 SSH别名登录

使用别名登录方式, 需要打开～/.ssh/config， 追加以下内容：

```
Host raspberrypi   			 #这里是别名
  HostName 192.169.31.48  #这里是服务器IP【注意这里开头空两格不是tab键】
  User haolee							#这里是用户名
```

`raspberrypi`是`haolee@192.168.31.48`的别名

## 03 SSH远程免密连接

<img src="https://raw.githubusercontent.com/conf-haolee/Images/master/uPic/55cb7d88c3a91dea5d91abf26f590e2c_720.png" alt="55cb7d88c3a91dea5d91abf26f590e2c_720" style="zoom:50%;" />

配置ssh 免密登录的原理：

把你本地的公钥添加到服务器的～/.ssh/authorized_keys文件里

> [【小知识】第6期 SSH免密登录的原理_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1y4411q7PW/?spm_id_from=333.1007.top_right_bar_window_history.content.click)
>
> [什么叫SSH？原理详解，看这一篇就够了！-ssh的原理 (51cto.com)](https://www.51cto.com/article/706122.html)

step1: 在本地生成密钥 `ssh-keygen`

step2: 连接上服务器，进入  `cd ~` 打开`.ssh/authorized_keys`，追加客户端下`id-rsa.pub`文件内容进去。

**快捷命令**:  `ssh-copy-id` `user@192.168.44.21`

可能遇到的问题

[解决：powershell无法使用ssh-copy-id命令 - octal_zhihao - 博客园 (cnblogs.com)](https://www.cnblogs.com/zhouzhihao/p/17087666.html)

## 04 基于SSH命令行文件传输

SCP 使用命令行实现文件传输， 使用一次命令传输一次

基本语法： `scp [可选参数] source_file target_file`

使用例子：

- 本地文件复制到远程： `scp local_file remote_username@remote_ip:remote_file`

- 远程目录复制到本地： `scp -r remote_username@remote_ip:remote_dir local_dir`

可选参数说明：

-r : 递归复制整个目录

## 05 可视化客户端SSH连接/FTP文件传输

作用： 使用UI软件实现ssh 连接，文件传输，连接一次可以多次传输文件。

Windows软件： `XFTP`  `XShell`

Mac软件： `Electerm`

Linux软件：`Remmina`

> 引用：

[SSH+免密登陆+VSCode远程开发+GitHub免密](https://www.bilibili.com/video/BV1Fep2e2EFr/?share_source=copy_web&vd_source=2b642316ba0d5f71a2bf75410183788c)