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
# 查询远程数据内容，对多语言问题做一个检查
async def fetch_and_check_data(connection_string):
    '''
    description: 连接到数据库并获取特定字段进行检查
    param {*} connection_string supabase连接字符串
    return {*}
    '''
    conn = None
    try:
        conn = await asyncpg.connect(dsn=connection_string, statement_cache_size=0)
        if conn:
            print("INFO: Connected to the database successfully.")
        
        async with conn.transaction():
            for id in range(14, 100):
                try:
                    query = f'SELECT * FROM {schema_name}.{table_name} WHERE id = $1'
                    row = await conn.fetchrow(query, id) 
                    
                    if row:
                        # check.check_language(language, llm.process_language(language, detail))
                        check_results = {}
                        for field in fields_to_check:
                            value = row[field]
                            lang_code = field.split('_')[-1]
                            check_results[field] = check.check_language(lang_code, value)
                            print(f"Check result for {field} (lang: {lang_code}) ID {row['id']}: {check_results[field]}")
                        
                        # return
                        update_query = f'''
                        UPDATE {schema_name}.{table_name}
                        SET {', '.join([f"{field} = ${i + 1}" for i, field in enumerate(fields_to_check)])}
                        WHERE id = ${len(fields_to_check) + 1}
                        '''
                        await conn.execute(update_query, *check_results.values(), row['id'])
                        print(f"Updated check results for ID {row['id']}.")
                except Exception as query_error:
                    print(f"ERROR: Query failed for ID {id}. Details: {query_error}")
                    continue
    except Exception as e:
        print("ERROR: Unable to connect to the database or execute query.")
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