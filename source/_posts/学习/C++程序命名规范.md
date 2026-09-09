---
title: C++程序命名规范
tags: 
- books
date: 2023-04-12 20:39:43 
permalink: /2023/04/12/cpp-naming-conventions/
categories:
- 学习
---

程序中最重要的一致性规则是命名管理。 命名的风格能让我们在不需要去查找类型声明的条件下快速地了解某个名字代表的含义：

**类型，变量，函数，常量，宏**等等。

<!-- more -->

# C++程序命名规定 #学习笔记

> 程序中最重要的一致性规则是命名管理。 命名的风格能让我们在不需要去查找类型声明的条件下快速地了解某个名字代表的含义：
>
> **类型，变量，函数，常量，宏**等等。



## 通用总则：

**函数命名，变量命名，文件命名要有描述性； 少用缩写。**

函数命名大驼峰，不用下划线。

变量命名全小写，单词间下划线连接，类的成员变量以下划线结尾\_



## 1 文件命名

文件名要全部小写， 可以包含下划线（_）或者连字符（\_），按照项目的约定，如果没有约定，最好是“\_”。

## 2. 类型命名

**总述**

类型名称的每个单词首字母均大写, 不包含下划线: `MyExcitingClass`, `MyExcitingEnum`.

所有类型命名 —— **类, 结构体, 类型定义 (`typedef`), 枚举, 类型模板参数** —— 均使用相同约定, 即以大写字母开始, 每个单词首字母均大写, 不包含下划线. 例如:

```
// 类和结构体
class UrlTable { ...
class UrlTableTester { ...
struct UrlTableProperties { ...

// 类型定义
typedef hash_map<UrlTableProperties *, string> PropertiesMap;

// using 别名
using PropertiesMap = hash_map<UrlTableProperties *, string>;

// 枚举
enum UrlTableErrors { ...
```



## 3. 变量命名

**总述**

变量 (包括函数参数) 和数据成员名**一律小写**, 单词之间用下划线连接. **类的成员变量以下划线结尾**, 但结构体的就不用, 如: `a_local_variable`, `a_struct_data_member`, `a_class_data_member_`.



## 4. 常量命名

**总述**

声明为 `constexpr` 或 `const` 的变量, 或在程序运行期间其值始终保持不变的, 命名时以 “k” 开头, 大小写混合. 例如:

```
const int kDaysInAWeek = 7;
```

## 5. 函数命名

一般来说, 函数名的每个单词首字母大写 (即 “**驼峰变量名” 或 “帕斯卡变量名”**), 没有下划线. 对于首字母缩写的单词, 更倾向于将它们视作一个单词进行首字母大写 (例如, 写作 `StartRpc()` 而非 `StartRPC()`).



## 6. 命名空间命名

**总述**

命名空间以小写字母命名. 最高级命名空间的名字取决于项目名称. 要注意避免嵌套命名空间的名字之间和常见的顶级命名空间的名字之间发生冲突.

## 7. 枚举命名

**总述**

枚举的命名应当和 [常量](https://zh-google-styleguide.readthedocs.io/en/latest/google-cpp-styleguide/naming/#constant-names) 或 [宏](https://zh-google-styleguide.readthedocs.io/en/latest/google-cpp-styleguide/naming/#macro-names) 一致: `kEnumName` 或是 `ENUM_NAME`.



## 8. 宏命名

**总述**

你并不打算 [使用宏](https://zh-google-styleguide.readthedocs.io/en/latest/google-cpp-styleguide/others/#preprocessor-macros), 对吧? 如果你一定要用, 像这样命名: `MY_MACRO_THAT_SCARES_SMALL_CHILDREN`.



## 引用：

[C++ 风格指南 - 内容目录 — Google 开源项目风格指南 (zh-google-styleguide.readthedocs.io)](https://zh-google-styleguide.readthedocs.io/en/latest/google-cpp-styleguide/contents.html)

