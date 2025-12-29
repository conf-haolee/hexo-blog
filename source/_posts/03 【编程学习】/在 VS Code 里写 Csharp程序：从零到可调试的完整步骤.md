---
title: 在 VS Code 里写 C# 程序：从零到可调试的完整步骤
date: 2025-12-21
tags: 
- C#
- vscode
categories:
- 编程学习
---

本文面向有 C++ 基础、需要在 VS Code 中练习 C# 的开发者，整理一条清晰、可复用的工作流：从创建项目、运行、到 F5 调试。

<!-- more-->

------

## 1. 前置准备

- 安装 .NET SDK（建议使用最新 LTS 或你项目需要的版本）
- VS Code 安装以下扩展之一
  - **C#**
  - **C# Dev Kit**（官方推荐，调试体验更完整）

------

## 2. 创建项目（Console 示例）

在项目目录打开终端，执行：

```
dotnet new console 
```

这会生成：

- *.csproj 项目文件
- Program.cs 入口文件
- bin/、obj/ 构建输出目录

------

## 3. 编写第一个练习程序

打开 Program.cs，写入你的练习代码（例如 struct/class 的区别）：

```c#
using System;

struct PointStruct { public int X, Y; }
class PointClass { public int X, Y; }

class Program
{
    static void Main()
    {
        var ps1 = new PointStruct { X = 1, Y = 2 };
        var ps2 = ps1;
        ps2.X = 9;
        Console.WriteLine($"struct: ps1.X={ps1.X}, ps2.X={ps2.X}");

        var pc1 = new PointClass { X = 1, Y = 2 };
        var pc2 = pc1;
        pc2.X = 9;
        Console.WriteLine($"class: pc1.X={pc1.X}, pc2.X={pc2.X}");
    }
}
```

------

## 4. 手动运行程序

在终端运行：

```
dotnet run 
```

输出应该类似：

```
struct: ps1.X=1, ps2.X=9 class: pc1.X=9, pc2.X=9 
```

------

## 5. 配置 F5 调试

VS Code 调试需要 launch.json 和 tasks.json。
请确保这些文件放在项目根目录下的 .vscode 文件夹里。

### 5.1 launch.json

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": ".NET Launch",
      "type": "coreclr",
      "request": "launch",
      "preLaunchTask": "build",
      "program": "${workspaceFolder}/bin/Debug/net9.0/vscodePrac.exe",
      "args": [],
      "cwd": "${workspaceFolder}",
      "stopAtEntry": false,
      "console": "internalConsole"
    }
  ]
}

```

> 注意：net9.0 请换成你 csproj 中的 TargetFramework。

### 5.2 tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "build",
      "command": "dotnet",
      "type": "process",
      "args": [
        "build",
        "${workspaceFolder}/vscodePrac.csproj"
      ],
      "problemMatcher": "$msCompile"
    }
  ]
}
```

------

## 6. 使用 F5 运行调试

- 打开 Program.cs
- 按 **F5**
- 断点即可生效，输出在调试控制台

------

## 7. 常见坑与排查

- **“无法提供调试配置”**
  通常是 launch.json 不在正确位置，或者没安装 C# 扩展
- **提示调试 XML**
  当前激活文件是 .csproj，切回 .cs 再按 F5
- **找不到可执行文件**
  launch.json 中路径错误，或 TargetFramework 写错

------

## 8. 推荐的练习流程

1. dotnet new console
2. 写代码
3. dotnet run 验证逻辑
4. 配置 F5 调试
5. 逐步理解 C# 与 C++ 差异