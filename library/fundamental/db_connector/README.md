# Supabase 数据库连接器使用指南

这是一个简单易用的 Supabase 数据库连接器，封装了常用的数据库 CRUD 操作。

## 快速开始

### 1. 环境配置

在项目根目录创建 `.env` 文件：

```env
SUPABASE_URL=your-supabase-project-url
SUPABASE_KEY=your-supabase-api-key
```

### 2. 初始化连接器

```python
from library.fundamental.db_connector import SupabaseConnector

# 方式1: 从环境变量自动读取
connector = SupabaseConnector()

# 方式2: 直接传入参数
connector = SupabaseConnector(
    url="your-supabase-url",
    key="your-supabase-key"
)
```

## 基础操作示例

### 插入数据 (Create)

**单条插入：**

```python
# 插入单条记录
data = {"name": "张三", "age": 25}
result = connector.insert("users", data)
print(result)
```

**批量插入：**

```python
# 插入多条记录
data = [
    {"name": "张三", "age": 25},
    {"name": "李四", "age": 30},
    {"name": "王五", "age": 28}
]
result = connector.insert("users", data)
print(f"插入了 {len(result)} 条记录")
```

### 查询数据 (Read)

**查询所有数据：**

```python
# 查询表中所有记录
all_users = connector.select("users")
```

**条件查询：**

```python
# 查询特定条件的记录
users = connector.select(
    table="users",
    filters={"age": 25}
)
```

**高级查询：**

```python
# 查询指定列，添加筛选、排序和限制
users = connector.select(
    table="users",
    columns="id, name, age",           # 指定列
    filters={"age": 25},                # 筛选条件
    order_by="created_at",              # 排序字段
    ascending=False,                     # 降序
    limit=10                            # 限制数量
)
```

### 更新数据 (Update)

```python
# 更新符合条件的记录
result = connector.update(
    table="users",
    data={"age": 26},                   # 要更新的数据
    filters={"name": "张三"}            # 筛选条件
)
print(f"更新了 {len(result)} 条记录")
```

### 删除数据 (Delete)

```python
# 删除符合条件的记录
result = connector.delete(
    table="users",
    filters={"name": "张三"}
)
print(f"删除了 {len(result)} 条记录")
```

### 更新或插入 (Upsert)

```python
# 如果记录存在则更新，不存在则插入
data = {"id": 1, "name": "张三", "age": 26}
result = connector.upsert("users", data)
```

### 计数 (Count)

**统计所有记录：**

```python
# 统计表中所有记录数
total = connector.count("users")
print(f"总共有 {total} 条记录")
```

**条件统计：**

```python
# 统计符合条件的记录数
count = connector.count(
    table="users",
    filters={"age": 25}
)
print(f"25岁的用户有 {count} 个")
```

## 完整示例

```python
from library.fundamental.db_connector import SupabaseConnector

# 初始化连接器
connector = SupabaseConnector()

# 1. 插入数据
new_user = {"name": "张三", "age": 25, "email": "zhangsan@example.com"}
inserted = connector.insert("users", new_user)
user_id = inserted[0]["id"]
print(f"插入用户，ID: {user_id}")

# 2. 查询数据
users = connector.select("users", filters={"id": user_id})
print(f"查询到用户: {users[0]['name']}")

# 3. 更新数据
updated = connector.update(
    "users",
    data={"age": 26},
    filters={"id": user_id}
)
print(f"更新用户年龄为: {updated[0]['age']}")

# 4. 统计记录
total = connector.count("users")
print(f"用户总数: {total}")

# 5. 删除数据
deleted = connector.delete("users", filters={"id": user_id})
print(f"删除了用户: {deleted[0]['name']}")
```

## 运行测试

项目包含一个完整的测试脚本 `test_supabase.py`，演示所有 CRUD 操作：

```bash
python library/fundamental/db_connector/test_supabase.py
```

## 注意事项

1. **环境变量优先**：优先从 `.env` 文件读取配置，也可以直接传参
2. **错误处理**：所有操作都会返回数据，建议添加适当的异常处理
3. **筛选条件**：`filters` 参数使用等值查询（`eq`），适用于大多数场景
4. **批量操作**：插入和更新支持传入列表进行批量操作
5. **主键冲突**：使用 `upsert` 方法可以避免主键冲突，自动判断插入或更新

## API 参考

### SupabaseConnector 类方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `insert(table, data)` | table: 表名<br>data: 字典或字典列表 | dict | 插入数据 |
| `select(table, columns, filters, limit, order_by, ascending)` | table: 表名<br>columns: 列名（默认 "*"）<br>filters: 筛选条件<br>limit: 限制数量<br>order_by: 排序字段<br>ascending: 升序/降序 | list[dict] | 查询数据 |
| `update(table, data, filters)` | table: 表名<br>data: 更新数据<br>filters: 筛选条件 | list[dict] | 更新数据 |
| `delete(table, filters)` | table: 表名<br>filters: 筛选条件 | list[dict] | 删除数据 |
| `upsert(table, data)` | table: 表名<br>data: 字典或字典列表 | list[dict] | 更新或插入 |
| `count(table, filters)` | table: 表名<br>filters: 筛选条件（可选） | int | 统计记录数 |

## 获取原始客户端

如果需要使用更高级的功能，可以获取底层的 Supabase 客户端：

```python
client = connector.client
# 使用原始客户端进行复杂查询
response = client.table("users").select("*").gte("age", 18).lte("age", 30).execute()
```

## 相关资源

- [Supabase 官方文档](https://supabase.com/docs)
- [Supabase Python SDK](https://github.com/supabase/supabase-py)
