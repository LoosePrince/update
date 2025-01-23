import os
import json
import base64
import requests
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置参数
GITHUB_API = "https://api.github.com/repos/MCDReforged/PluginCatalogue/contents/plugins"
# 在代码开头修改HEADERS配置：
GITHUB_TOKEN = "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"  # 需要创建
HEADERS = {
    'User-Agent': 'MCDReforged-Plugin-Scraper',
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}
SSL_VERIFY = True  # 设置为True如果网络环境正常
TIMEOUT = 15
RETRY_COUNT = 3

def create_session():
    session = requests.Session()
    retries = Retry(
        total=RETRY_COUNT,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def fetch_version(plugin_name):
    """获取插件版本"""
    url = f"https://mcdreforged.com/zh-CN/plugin/{plugin_name}?_rsc=1rz10"
    try:
        response = requests.get(url, timeout=5, verify=SSL_VERIFY)
        response.raise_for_status()
        match = re.search(rf'/plugin/{plugin_name}/release/([\d\.]+)', response.text)
        print(f"获取版本成功 {plugin_name}: {match.group(1)}")
        return match.group(1) if match else None
    except Exception as e:
        print(f"获取版本失败 {plugin_name}: {str(e)}")
        return None

def get_plugin_versions(plugin_dict):
    """
    获取插件版本信息
    """
    results = {}
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_plugin = {executor.submit(fetch_version, name): name for name in plugin_dict.values()}
        for future in as_completed(future_to_plugin):
            plugin_name = future_to_plugin[future]
            try:
                version = future.result()
                results[plugin_name] = version
            except Exception:
                results[plugin_name] = None

    return results

def get_plugins_info():
    """获取所有插件信息"""
    plugins = []
    plugin_dict = {}
    
    try:
        session = create_session()
        response = session.get(
            GITHUB_API,
            headers=HEADERS,
            timeout=TIMEOUT,
            verify=SSL_VERIFY
        )
        response.raise_for_status()
        
        for item in response.json():
            if item['type'] == 'dir':
                plugin_name = item['name']
                try:
                    info_response = session.get(
                        f"{GITHUB_API}/{plugin_name}/plugin_info.json",
                        headers=HEADERS,
                        timeout=TIMEOUT,
                        verify=SSL_VERIFY
                    )
                    info_response.raise_for_status()
                    
                    content = base64.b64decode(info_response.json()['content']).decode('utf-8')
                    plugin_info = json.loads(content)
                    
                    # 构造仓库链接
                    repo_url = f"{plugin_info['repository']}/tree/{plugin_info['branch']}"
                    if plugin_info.get('related_path'):
                        repo_url += f"/{plugin_info['related_path']}"
                        
                    plugin_data = {
                        "id": plugin_info['id'],
                        "authors": [{"name": a['name'], "link": a['link']} for a in plugin_info['authors']],
                        "repository_url": repo_url,
                        "labels": plugin_info['labels'],
                    }
                    plugins.append(plugin_data)
                    plugin_dict[plugin_info['id']] = plugin_info['id']
                    print(f"获取 {plugin_name} 信息成功")
                    
                except Exception as e:
                    print(f"获取 {plugin_name} 信息失败: {str(e)}")
                    continue

        # 获取版本信息（保持原有逻辑）
        versions = get_plugin_versions(plugin_dict)
        for plugin in plugins:
            plugin["latest_version"] = versions.get(plugin["id"], None)

    except Exception as e:
        print(f"主流程错误: {str(e)}")

    return plugins

def save_plugins_data(plugins):
    """
    保存插件数据到JSON文件
    """
    output_dir = "./data"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "plugins.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(plugins, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # 测试网络连接
    try:
        test_response = requests.get("https://api.github.com", timeout=5, verify=SSL_VERIFY)
        print("GitHub API连接测试:", "成功" if test_response.ok else "失败")
    except Exception as e:
        print("网络连接测试失败:", str(e))
        exit(1)

    plugins_info = get_plugins_info()
    save_plugins_data(plugins_info)
    print(f"成功保存 {len(plugins_info)} 个插件信息到 /data/plugins.json")