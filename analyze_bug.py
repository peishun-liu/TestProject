#!/usr/bin/env python3
"""
Bug分析脚本 - 使用DevToolBox AI检测Repro Steps中的中文
"""

import os
import re
import sys
import json
import requests
from typing import Dict, Any, List


def extract_text_from_html(html_text: str) -> str:
    """从HTML中提取纯文本，去掉所有标签"""
    return re.sub(r'<[^>]*>', ' ', html_text)


def call_ai_api(bug_id: str, repro_steps: str) -> Dict[str, Any]:
    """
    调用DevToolBox AI API分析Repro Steps中是否包含中文
    
    Args:
        bug_id: Bug ID
        repro_steps: 清理后的Repro Steps文本
        
    Returns:
        AI API的响应结果
        
    Raises:
        requests.RequestException: 如果API调用失败
    """
    prompt = f"""あなたはプロフェッショナルなソフトウェアエンジニアです。

Bug ID：
{bug_id}

Repro Steps：
{repro_steps}

Repro Stepsの中に中国語が含まれているか判定してください。

ルール：
- 中国語が含まれている場合、has_chineseをtrueにしてください。
- 中国語がない場合、chinese_textは空の配列にしてください。

必ず以下のJSON形式だけを返してください。

{{
  "has_chinese": false,
  "chinese_text": []
}}

JSON以外の文章は絶対に返さないでください"""

    payload = {
        "prompt": prompt,
        "max_tokens": 500
    }
    
    response = requests.post(
        "https://devtoolbox-api.devtoolbox-api.workers.dev/ai/generate",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    response.raise_for_status()
    
    return response.json()


def update_work_item(bug_id: str, token: str) -> None:
    """
    在Azure DevOps中更新Work Item，添加ChineseDetected标签
    
    Args:
        bug_id: Bug ID
        token: Azure DevOps认证令牌
        
    Raises:
        requests.RequestException: 如果API调用失败
    """
    url = (
        f"https://dev.azure.com/qualica-sbu/TestGERP/_apis/wit/workitems/"
        f"{bug_id}?api-version=7.1"
    )
    
    patch_data = [
        {
            "op": "add",
            "path": "/fields/System.Tags",
            "value": "ChineseDetected"
        }
    ]
    
    response = requests.patch(
        url,
        json=patch_data,
        headers={
            "Content-Type": "application/json-patch+json",
            "Authorization": f"Bearer {token}"
        },
        timeout=30
    )
    response.raise_for_status()


def main() -> None:
    """主程序入口"""
    
    # 从环境变量获取参数
    bug_id = os.getenv("BUG_ID")
    repro_steps_raw = os.getenv("REPRO_STEPS")
    system_token = os.getenv("SYSTEM_ACCESSTOKEN")
    
    if not all([bug_id, repro_steps_raw, system_token]):
        print("Error: Missing required environment variables")
        print("Required: BUG_ID, REPRO_STEPS, SYSTEM_ACCESSTOKEN")
        sys.exit(1)
    
    # 清理Repro Steps中的HTML标签
    clean_text = extract_text_from_html(repro_steps_raw)
    
    print("=" * 40)
    print("入力内容：")
    print("=" * 40)
    print(clean_text)
    print()
    
    try:
        # 调用AI API
        ai_response = call_ai_api(bug_id, clean_text)
        
        # 提取结果
        ai_result = ai_response.get("response", {})
        has_chinese = ai_result.get("has_chinese", False)
        chinese_text = ai_result.get("chinese_text", [])
        
        print(f"Has Chinese: {has_chinese}")
        print(f"Chinese Text: {json.dumps(chinese_text)}")
        print()
        
        # 如果检测到中文，更新Work Item
        if has_chinese:
            print("Chinese detected")
            update_work_item(bug_id, system_token)
            print(f"Successfully added 'ChineseDetected' tag to Bug {bug_id}")
        else:
            print("No Chinese detected.")
            
    except requests.RequestException as e:
        print(f"Error calling API: {e}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, ValueError) as e:
        print(f"Error parsing response: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
