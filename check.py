import json
import asyncio
import asyncpg
import csv
import os
from datetime import datetime
from dotenv import load_dotenv
from util.checkdata_util import CheckUtil
from config import fields_to_check
load_dotenv()
check = CheckUtil()
# 环境名称
env = os.getenv('CURRENT_ENV')
if env == 'develop':
    schema_name="ziniao_test"
else:
    schema_name="ziniao"
print('模式名字',schema_name)
table_name = "web_navigation"
# 设置最大重试次数和等待时间
MAX_RETRIES = 5
RETRY_WAIT_TIME = 3  # seconds

async def handle_retry(retries):
    if retries < MAX_RETRIES:
        wait_time = RETRY_WAIT_TIME * (retries + 1)  # Exponential backoff
        print(f"INFO: Waiting for {wait_time} seconds before retrying...")
        await asyncio.sleep(wait_time)
    else:
        print(f"ERROR: Exceeded maximum retry limit.")

async def fetch_and_check_data(connection_string):
    '''
    description: 连接到数据库并获取特定字段进行检查
    param {*} connection_string supabase连接字符串
    return {*}
    '''
    conn = None
    retries = 0
    current_id = 323

    try:
        # 只在开始时连接数据库
        conn = await asyncpg.connect(dsn=connection_string, statement_cache_size=0)
        if conn:
                print("INFO: Connected to the database successfully.")
        
        while current_id < 1300:
            try:
                async with conn.transaction():
                    query = f'SELECT * FROM {schema_name}.{table_name} WHERE id = $1'
                    row = await conn.fetchrow(query, current_id)

                    if row:
                        # 执行检查操作
                        check_results = {}
                        for field in fields_to_check:
                            value = row[field]
                            lang_code = field.split('_')[-1]
                            check_results[field] = check.check_language(lang_code, value)
                            print(f"Check result for {field} (lang: {lang_code}) ID {row['id']}: {check_results[field]}")
                        
                        # 更新数据库
                        update_query = f'''
                        UPDATE {schema_name}.{table_name}
                        SET {', '.join([f"{field} = ${i + 1}" for i, field in enumerate(fields_to_check)])}
                        WHERE id = ${len(fields_to_check) + 1}
                        '''
                        await conn.execute(update_query, *check_results.values(), row['id'])
                        print(f"Updated check results for ID {row['id']}.")
                    
                current_id += 1
                retries = 0  # 成功后重置重试次数

            except asyncpg.PostgresConnectionError as conn_error:
                print(f"ERROR: Connection lost for ID {current_id}. Retrying... Details: {conn_error}")
                await handle_retry(retries)
                retries += 1
                if retries > MAX_RETRIES:
                    print(f"ERROR: Max retries reached. Skipping ID {current_id}.")
                    current_id += 1  # 跳过当前ID
                    retries = 0
                else:
                    # 重新建立连接
                    conn = await asyncpg.connect(dsn=connection_string, statement_cache_size=0)
                    print("INFO: Reconnected to the database successfully.")

            except Exception as e:
                print(f"ERROR: Query failed for ID {current_id}. Details: {e}")
                current_id += 1  # 跳过当前ID
                retries = 0  # 重置重试次数

    except Exception as e:
        print("ERROR: Unable to connect to the database.")
        print(e)

    finally:
        if conn:
            await conn.close()
            print("INFO: Connection closed.")

async def main():
   supabass_url = os.getenv('CONNECTION_SUPABASE_URL')
   print(supabass_url)
   await fetch_and_check_data(supabass_url)


if __name__ == "__main__":
    asyncio.run(main())