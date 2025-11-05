#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密码设置工具
用于生成 Web 密码的哈希值
"""

import sys
from werkzeug.security import generate_password_hash

def main():
    print("=" * 60)
    print("NovelGrok 密码设置工具")
    print("=" * 60)
    print()
    
    if len(sys.argv) > 1:
        # 从命令行参数读取密码
        password = sys.argv[1]
    else:
        # 交互式输入密码
        password = input("请输入新密码: ").strip()
        
        if not password:
            print("❌ 密码不能为空")
            sys.exit(1)
        
        confirm = input("请再次输入密码: ").strip()
        
        if password != confirm:
            print("❌ 两次输入的密码不一致")
            sys.exit(1)
    
    # 生成密码哈希
    password_hash = generate_password_hash(password)
    
    print()
    print("✅ 密码哈希生成成功！")
    print()
    print("请将以下内容添加到 .env 文件中:")
    print("-" * 60)
    print(f"WEB_PASSWORD_HASH={password_hash}")
    print("-" * 60)
    print()
    print("注意:")
    print("1. 如果 .env 文件中已存在 WEB_PASSWORD_HASH，请替换它")
    print("2. 修改后需要重启 Web 服务才能生效")
    print("3. 请妥善保管您的密码，哈希值无法反向解密")
    print()

if __name__ == '__main__':
    main()
