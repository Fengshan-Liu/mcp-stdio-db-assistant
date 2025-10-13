from mcp.server.fastmcp import FastMCP
import mcp.types as types
import os
from threading import local
import threading

from sqlalchemy import (
    create_engine, MetaData, text, select, or_, String, Text, Integer, Column,BigInteger, Numeric, DateTime, DDL, Table
)
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base


import atexit


# 加载系统prompt
def load_system_prompt():
    """加载MCP_prompt.txt文件内容"""
    prompt_file = "MCP_Prompt.txt"
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "系统提示文件未找到，使用默认配置"
    except Exception as e:
        return f"读取提示文件时出错: {str(e)}"

# 线程本地存储替代全局变量
thread_data = local()

# 全局常量（只读，线程安全）
SYSTEM_PROMPT = load_system_prompt()

def get_thread_data():
    """获取当前线程的数据存储"""
    if not hasattr(thread_data, 'engine'):
        thread_data.engine = None
        thread_data.metadata = MetaData()
        thread_data.table_names = None
        thread_data.connected_database = None
    return thread_data

def cleanup_thread_connection():
    """清理当前线程的数据库连接"""
    data = get_thread_data()
    if data.engine:
        try:
            data.engine.dispose()
        except Exception:
            pass  # 忽略清理时的错误
        finally:
            data.engine = None
            data.metadata = MetaData()
            data.table_names = None
            data.connected_database = None

# 初始化FastMCP
mcp = FastMCP("stdio_server")

# --- 系统工具 ---

@mcp.tool()
def get_system_prompt() -> str:
    """获取系统提示和使用指南
    
    Returns:
        str: 系统prompt内容，包含使用指南和注意事项
    """
    return SYSTEM_PROMPT

@mcp.tool()
def get_server_status() -> dict:
    """获取MCP服务器状态信息
    
    Returns:
        dict: 服务器状态信息
    """
    data = get_thread_data()
    return {
        "server_name": "MultiClientDBServer",
        "database_connected": data.engine is not None,
        "connected_database": data.connected_database,
        "available_tables": data.table_names if data.table_names else [],
        "system_prompt_loaded": bool(SYSTEM_PROMPT),
        "prompt_preview": SYSTEM_PROMPT[:200] + "..." if len(SYSTEM_PROMPT) > 200 else SYSTEM_PROMPT,
        "thread_id": threading.get_ident()  # 用于调试多线程问题
    }

# --- 数据库工具 ---

@mcp.tool()
def connect_to_database_and_list_tables(database: str ="scrb_test"):
    """连接到MySQL数据库并获取表列表
    
    重要提示：请遵循系统指导原则进行操作
    每个客户端会话都有独立的数据库连接
    
    Args:
        database (str): 要连接的数据库名称
    Returns:
        dict: 包含成功消息和表名列表，或错误信息。
    """
    data = get_thread_data()
    
    # 如果已经有连接，先安全地关闭它
    cleanup_thread_connection()

    try:
        data.engine = create_engine(
            f"mysql+pymysql://root:123456@localhost:3306/{database}",
            poolclass=QueuePool,
            pool_size=3,  # 减少每个线程的连接池大小
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=1800
        )
        
        # 测试连接
        with data.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # 反射表结构
        data.metadata = MetaData()
        data.metadata.reflect(bind=data.engine)
        data.table_names = list(data.metadata.tables.keys())
        data.connected_database = database
        
        return {
            "status": "success",
            "message": f"成功连接到数据库 '{database}'。",
            "available_tables": data.table_names,
            "system_guidance": "请按照系统提示进行后续操作",
            "connection_info": f"线程 {threading.get_ident()} 已连接到 {database}"
        }

    except SQLAlchemyError as e:
        cleanup_thread_connection()
        return {"error": f"数据库连接或获取表失败: {str(e)}"}
    except Exception as e:
        cleanup_thread_connection()
        return {"error": f"发生未知错误: {str(e)}"}



@mcp.tool()
def get_table_schema(table_name: str) -> dict:
    """获取表结构信息
    
    Args:
        table_name (str): 要查询其结构的表的名称。
    Returns:
        dict: 包含表结构信息的字典，或错误信息。
    """
    data = get_thread_data()
    if not data.engine:
        return {"error": "数据库未连接。请先调用 'connect_to_database_and_list_tables'"}

    try:
        target_table = data.metadata.tables.get(table_name)
        if target_table is None:
            # 尝试刷新表结构
            data.metadata.reflect(bind=data.engine, only=[table_name])
            target_table = data.metadata.tables.get(table_name)
            
        if target_table is None:
            return {"error": f"表 '{table_name}' 在数据库中不存在。"}
        
        columns_info = []
        for col in target_table.columns:
            columns_info.append({
                "name": col.name,
                "type": str(col.type),
                "primary_key": col.primary_key,
                "nullable": col.nullable,
                "comment": col.comment or "",
                "foreign_keys": [str(fk) for fk in col.foreign_keys]
            })
        
        return {
            "table_name": table_name,
            "columns": columns_info,
            "total_columns": len(columns_info),
            "database": data.connected_database
        }
    except Exception as e:
        return {"error": f"获取表结构时发生错误: {str(e)}"}
        


@mcp.tool()
def search_across_all_tables(search_term: str):
    """在数据库的所有表中搜索包含指定字符串的记录
    
    支持对文本、数字和日期时间类型的列进行模糊搜索。
    
    Args:
        search_term: 要搜索的关键词，只用包含关键词，不用添加任何修饰如：频道id为4，那就直接是4
    Returns:
        dict: 包含搜索结果的字典。
    """
    data = get_thread_data()
    if not data.engine:
        return {"error": "数据库未连接。请先调用 'connect_to_database_and_list_tables'。"}

    all_results = []
    try:
        # 刷新表结构以获取最新信息
        data.metadata.reflect(bind=data.engine)
        
        for table_name, table in data.metadata.tables.items():
            conditions = []
            for col in table.columns:
                if isinstance(col.type, (String, Text, Integer, BigInteger, Numeric, DateTime)):
                    conditions.append(col.cast(String).like(f"%{search_term}%"))

            if not conditions:
                continue

            stmt = select(table).where(or_(*conditions))
            with data.engine.connect() as conn:
                result_rows = conn.execute(stmt).fetchall()
                for row in result_rows:
                    all_results.append({
                        "found_in_table": table_name,
                        "data": dict(row._mapping) 
                    })

        if not all_results:
            return {
                "status": "not_found", 
                "message": f"在所有表中均未找到包含 '{search_term}' 的记录。",
                "database": data.connected_database
            }
            
        return {
            "results": all_results,
            "total_matches": len(all_results),
            "search_term": search_term,
            "database": data.connected_database
        }
    except Exception as e:
        return {"error": f"跨表搜索时发生错误: {str(e)}"}
    
@mcp.tool()
def get_data_in_conditions(
    search_items: list,
    table_name: str,
    column_to_search: list,
    columns_to_return: list,
    return_table_info: bool = False
) -> dict:
    """在指定列中搜索关键词，返回匹配的行数据（优先使用此工具进行精确查询）
    
    Args:
        search_items (list): 要搜索的关键词列表,用户输入
        table_name (str): 表名,table_names中的一个
        column_to_search (list): 用于搜索的列名列表
        columns_to_return (list): 要返回的列名列表
        return_table_info (bool): 是否只返回表结构信息,默认False
    Returns:
        dict: 匹配的行数据列表（字典格式）或表结构信息
    """
    data = get_thread_data()
    if not data.engine:
        return {"error": "数据库未连接。请先调用 'connect_to_database_and_list_tables'"}

    try:
        # 刷新表结构
        data.metadata.reflect(bind=data.engine)
        table = data.metadata.tables.get(table_name)
        if table is None:
            return {"error": f"表 '{table_name}' 在数据库中不存在。"}

        # 如果只需要返回表结构信息
        if return_table_info:
            columns_info = [col.name for col in table.columns]
            return {
                "table_name": table.name,
                "columns": columns_info,
                "database": data.connected_database
            }
            
        # 验证列名是否存在
        table_columns = [col.name for col in table.columns]
        
        # 检查搜索列是否存在
        for col in column_to_search:
            if col not in table_columns:
                return {"error": f"搜索列 '{col}' 在表 '{table_name}' 中不存在。可用列: {table_columns}"}
        
        # 检查返回列是否存在
        for col in columns_to_return:
            if col not in table_columns:
                return {"error": f"返回列 '{col}' 在表 '{table_name}' 中不存在。可用列: {table_columns}"}
            
        # 检验表是否在当前连接的数据库中
        if data.table_names and table_name not in data.table_names:
            return {"error": f"表 '{table_name}'不存在。可用表: {data.table_names}"}

        # 构建搜索条件
        conditions = []
        for col_name in column_to_search:
            for search_item in search_items:
                if isinstance(search_item, str):
                    conditions.append(table.c[col_name].like(f"%{search_item}%"))
                else:
                    conditions.append(table.c[col_name] == search_item)

        # 构建 SELECT 字段
        selected_columns = [table.c[col] for col in columns_to_return]
        stmt = select(*selected_columns)
        
        # 添加搜索条件
        if conditions:
            stmt = stmt.where(or_(*conditions))

        # 执行查询
        with data.engine.connect() as conn:
            result = conn.execute(stmt)
            rows = [dict(row._mapping) for row in result]
            
            # 如果没有查询结果，返回明确信息
            if not rows:
                return {
                    "message": "查询结果为空，未找到匹配的数据", 
                    "count": 0,
                    "database": data.connected_database
                }
            
            return {
                "data": rows,
                "count": len(rows),
                "table_name": table_name,
                "search_items": search_items,
                "columns_searched": column_to_search,
                "columns_returned": columns_to_return,
                "database": data.connected_database
            }

    except Exception as e:
        return {"error": f"查询执行失败: {str(e)}"}


@mcp.tool()
def deduplicate(target: list):
    """去重工具

    Args:
        target (list): 需要去重的字典列表

    Returns:
        list: 去重后的字典列表
    """
    result = []
    seen = set()
    for item in target:
        # 使用 frozenset 作为唯一标识符
        identifier = frozenset(item.items())
        if identifier not in seen:
            seen.add(identifier)
            result.append(item)
    return result


    



@mcp.tool()
def get_table_structure_into_sql(table_name: str, table_structure_info: str = "tables_structure"):
    """
    获取指定表的字段信息，并以表名作为列名存储到横向结构的表中
    
    功能：
    - 读取目标表的所有字段名称和注释
    - 在存储表中创建以目标表名为列名的新列
    - 将字段名和注释组合后存储在该列中
    
    参数：
        table_name: 要获取结构的目标表名
        table_structure_info: 存储表结构信息的表名，默认为 'tables_structure'
    
    返回值：
        dict: 操作结果信息
    """
    data = get_thread_data()
    
    # 检查数据库连接
    if not data.engine:
        return {"error": "数据库未连接。请先调用 'connect_to_database_and_list_tables'"}

    try:
        # 获取目标表结构
        data.metadata.reflect(bind=data.engine, only=[table_name])
        target_table = data.metadata.tables.get(table_name)
        
        if target_table is None:
            return {"error": f"表 '{table_name}' 在数据库中不存在。"}
        
        # 获取字段名称和注释，组合成字符串
        columns_info = []
        for col in target_table.columns:
            # 组合格式：字段名 (注释) 或者 字段名：注释
            if col.comment:
                field_info = f"{col.name} ({col.comment})"
            else:
                field_info = col.name
            columns_info.append(field_info)
        
        # 将所有字段信息合并成一个字符串，用换行符分隔
        combined_info = "\n".join(columns_info)
        
        # 检查存储表是否存在
        if table_structure_info not in data.metadata.tables:
            # 创建基础存储表
            structure_table = Table(
                table_structure_info,
                data.metadata,
                Column('id', Integer, primary_key=True, autoincrement=True, comment='行ID'),
                comment='表结构信息存储表'
            )
            structure_table.create(data.engine, checkfirst=True)
            
            # 插入第一行数据
            with data.engine.begin() as conn:
                conn.execute(structure_table.insert().values())
            
            # 刷新元数据
            data.metadata.reflect(bind=data.engine, only=[table_structure_info])
        
        # 获取存储表对象
        structure_table = data.metadata.tables[table_structure_info]
        
        # 检查是否已存在该表名的列
        column_exists = table_name in [col.name for col in structure_table.columns]
        
        if not column_exists:
            # 添加新列（以表名命名）
            with data.engine.begin() as conn:
                # 动态添加列的SQL
                add_column_sql = f"""
                ALTER TABLE {table_structure_info} 
                ADD COLUMN `{table_name}` TEXT COMMENT '{table_name}表的字段信息'
                """
                conn.execute(DDL(add_column_sql))
            
            # 刷新元数据以获取新列
            data.metadata.clear()
            data.metadata.reflect(bind=data.engine, only=[table_structure_info])
            structure_table = data.metadata.tables[table_structure_info]
        
        # 更新该列的数据
        with data.engine.begin() as conn:
            if not column_exists:
                # 如果是新添加的列，需要重新获取表结构
                data.metadata.clear()
                data.metadata.reflect(bind=data.engine, only=[table_structure_info])
                structure_table = data.metadata.tables[table_structure_info]
            
            # 使用原生SQL来操作，避免SQLAlchemy对象引用问题
            try:
                # 检查是否有数据行
                from sqlalchemy import text
                select_sql = text(f"SELECT id FROM {table_structure_info} LIMIT 1")
                result = conn.execute(select_sql).fetchone()
                
                if not result:
                    # 插入第一行数据
                    if column_exists:
                        # 如果列已存在，插入时包含该列
                        insert_sql = text(f"INSERT INTO {table_structure_info} (`{table_name}`) VALUES (:data)")
                        conn.execute(insert_sql, {"data": combined_info})
                    else:
                        # 如果是新列，先插入基础行，再更新
                        insert_sql = text(f"INSERT INTO {table_structure_info} (id) VALUES (1)")
                        conn.execute(insert_sql)
                        update_sql = text(f"UPDATE {table_structure_info} SET `{table_name}` = :data WHERE id = 1")
                        conn.execute(update_sql, {"data": combined_info})
                    action = "inserted"
                else:
                    # 更新现有行的对应列
                    update_sql = text(f"UPDATE {table_structure_info} SET `{table_name}` = :data WHERE id = :row_id")
                    conn.execute(update_sql, {"data": combined_info, "row_id": result[0]})
                    action = "updated"
                    
            except Exception as e:
                return {"error": f"数据操作错误: {str(e)}"}
        
        return {
            "success": True,
            "message": f"成功将表 '{table_name}' 的 {len(columns_info)} 个字段信息存储到 '{table_structure_info}' 表的 '{table_name}' 列中",
            "source_table": table_name,
            "columns_count": len(columns_info),
            "storage_table": table_structure_info,
            "column_name": table_name,
            "action": action,
            "field_info": combined_info
        }
        
    except SQLAlchemyError as e:
        return {"error": f"数据库操作错误: {str(e)}"}
    except Exception as e:
        return {"error": f"获取表结构时发生错误: {str(e)}"}
        


        
    
    
    
    
# 添加连接清理的钩子
def cleanup_on_exit():
    """程序退出时清理所有连接"""
    try:
        cleanup_thread_connection()
    except Exception:
        atexit.register(cleanup_on_exit)

if __name__ == "__main__":
    mcp.run(transport="stdio")