---
title: Hexo发布指南及入门
tags: 
- hexo
categories:
- 速查手册
---
`hexo g`  生成静态文件; `hexo s`  启动服务; `hexo d`  远程部署

Welcome to [Hexo](https://hexo.io/)! This is your very first post. Check [documentation](https://hexo.io/docs/) for more info. If you get any problems when using Hexo, you can find the answer in [troubleshooting](https://hexo.io/docs/troubleshooting.html) or you can ask me on [GitHub](https://github.com/hexojs/hexo/issues).

<!-- more -->

## Quick Start

### Create a new post

``` bash
$ hexo new "My New Post"
```

More info: [Writing](https://hexo.io/docs/writing.html)

### Run server

``` bash
$ hexo server
```

More info: [Server](https://hexo.io/docs/server.html)

### Generate static files

``` bash
$ hexo generate
```

More info: [Generating](https://hexo.io/docs/generating.html)

### Deploy to remote sites

``` bash
$ hexo deploy
```

More info: [Deployment](https://hexo.io/docs/one-command-deployment.html)

## 1.创建文章

`hexo new firstnote.md`

时 使用分类 和标签

`hexo g`  生成静态文件

`hexo s`  启动服务

`hexo d`  远程部署

> 引用

[指令 | Hexo](https://hexo.io/zh-cn/docs/commands.html)

## 2. hexo 主题修改 volantis

### 开启搜索（Search）

6.0默认开启

1. 需要先安装插件

   ```
   npm i hexo-generator-json-content
   ```

2. 如需配置，如下

   ```_config.volantis.yml
   search:
     enable: true
     service: hexo
   ```

### 开启公式渲染

https://volantis.js.org/v6/page-settings/#%E6%B8%B2%E6%9F%93%E5%85%AC%E5%BC%8F



> [Hexo-Volantis主题优化 - 小TiD笔记 (tidnotes.top)](https://main.tidnotes.top/post/hexo-volantis主题优化/#插件（Plugins）)

> [Volantis 主题用户手册](https://inkss.cn/page/notes/001-Volantis%E4%B8%BB%E9%A2%98%E7%94%A8%E6%88%B7%E6%89%8B%E5%86%8C.html)
>
> [在Hexo博文中嵌入Jupyter notebook](https://coding.f10.org/Python/Jupyterlab/%E5%9C%A8Hexo%E5%8D%9A%E6%96%87%E4%B8%AD%E5%B5%8C%E5%85%A5Jupyter%20notebook/)
>
> [Hexo博客搭建 美化篇 Volantis](https://busyogg.github.io/article/38effc2a84e9/#%E7%95%8C%E9%9D%A2%E7%BE%8E%E5%8C%96%EF%BC%88%E4%BB%A3%E7%A0%81%E5%9D%97%E3%80%81%E6%A0%87%E9%A2%98%EF%BC%89)

## hexo部署与调试

```
$ hexo clean //清除静态页面缓存（清除 public 文件夹)         
$ hexo g     //在本地生成静态页面（生成 public 文件夹）        
$ hexo s     //启动本地服务 http://localhost:4000，进行预览调试           
$ hexo d     //远程部署，同步到 GitHub         

$ npm install hexo-deployer-git --save    //自动部署
$ hexo clean && hexo g && hexo d          //发布
```

# hexo 相关功能设置

在hexo文件夹下右键点击Git Base here后键入$hexo new page “name”，source/_post 文件夹中生成name.md文件，打开后即可编辑，编辑格式如下：

```
title: 文章名
date: 2017-10-31 20:38:17     //发表日期
updated: 2017-10-31 21:58:03  //更新日期
categories: Life              //文章分类
tags: [tag1,tag2]             //文章标签，多标签时使用英文逗号隔开
photos:                       //如果使用Fancybox（文章头部展示图片），如此设置  
                              //注意冒号后面有空格
```

## 开启文章搜索



## 摘要居中显示图片

```
/<div align="center">
<img src=https://---.png width=400px />
</div>
```

```
<!-- more -->
```



## 文章摘要部分

在要显示的文字末尾添加如下代码实现文章在主页的折叠显示。

```java
<!-- more -->
```

## 文章加密

```text
# 安装插件
npm install --save hexo-blog-encrypt
```

**修改文章信息头如下：**

```java
title: Hello World
tags:
- 加密文章tag
date: 2020-03-13 21:12:21
password: muyiio
abstract: 这里有东西被加密了，需要输入密码查看哦。
message: 您好，这里需要密码。
wrong_pass_message: 抱歉，这个密码看着不太对，请再试试。
wrong_hash_message: 抱歉，这个文章不能被纠正，不过您还是能看看解密后的内容。
---
```

- **对博客[根目录](https://zhida.zhihu.com/search?content_id=113293931&content_type=Article&match_order=1&q=根目录&zhida_source=entity)_config添加如下字段：**

```text
# 安全
encrypt: # hexo-blog-encrypt
  abstract: 这里有东西被加密了，需要输入密码查看哦。
  message: 您好, 这里需要密码.
  tags:
  - {name: tagName, password: 密码A}
  - {name: tagName, password: 密码B}
  template: <div id="hexo-blog-encrypt" data-wpm="{{hbeWrongPassMessage}}" data-whm="{{hbeWrongHashMessage}}"><div class="hbe-input-container"><input type="password" id="hbePass" placeholder="{{hbeMessage}}" /><label>{{hbeMessage}}</label><div class="bottom-line"></div></div><script id="hbeData" type="hbeData" data-hmacdigest="{{hbeHmacDigest}}">{{hbeEncryptedData}}</script></div>
  wrong_pass_message: 抱歉, 这个密码看着不太对, 请再试试.
  wrong_hash_message: 抱歉, 这个文章不能被校验, 不过您还是能看看解密后的内容.
```



> 引用

[Hexo与MarkDown_hexo markdown_小老弟偶的博客-CSDN博客](https://blog.csdn.net/qq_42446156/article/details/107888057)

[对 Hexo 博客文章进行加密](https://zhuanlan.zhihu.com/p/113235573)

