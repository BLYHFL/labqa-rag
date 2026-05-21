#!/bin/bash
# ============================================
# LabQA 文档预处理管道
# 将 raw-docs/ 中的多格式文件转换为 Markdown
# 归入 context/ 对应目录
# ============================================

set -e

RAW_DIR="raw-docs"
CONTEXT_DIR=".opencode/context"
TEMP_DIR="/tmp/labqa-convert-$$"
LOG_FILE="/tmp/labqa-convert.log"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 统计变量
NEW_COUNT=0
UPDATE_COUNT=0
SKIP_COUNT=0
FAIL_COUNT=0

echo "=========================================="
echo "  LabQA 知识库更新"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

mkdir -p "$TEMP_DIR"
mkdir -p "$CONTEXT_DIR/devices"
mkdir -p "$CONTEXT_DIR/projects"
mkdir -p "$CONTEXT_DIR/knowledge/论文笔记"
mkdir -p "$CONTEXT_DIR/guides"

# ---------- 转换函数 ----------

convert_docx() {
    local input="$1"
    local output="$2"
    echo -n "  📄 转换 DOCX: $(basename "$input") ... "
    if python3 -c "
import sys
try:
    from docx import Document
    doc = Document('$input')
    with open('$output', 'w', encoding='utf-8') as f:
        for para in doc.paragraphs:
            f.write(para.text + '\n')
        for table in doc.tables:
            f.write('\n')
            for row in table.rows:
                f.write('| ' + ' | '.join(cell.text for cell in row.cells) + ' |\n')
    print('OK')
except ImportError:
    print('SKIP (python-docx not installed)')
    sys.exit(1)
except Exception as e:
    print(f'FAIL: {e}')
    sys.exit(1)
" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${YELLOW}SKIP (python-docx 未安装)${NC}"
        return 1
    fi
}

convert_pptx() {
    local input="$1"
    local output="$2"
    echo -n "  📊 转换 PPTX: $(basename "$input") ... "
    if python3 -c "
import sys
try:
    from pptx import Presentation
    prs = Presentation('$input')
    img_dir = '$CONTEXT_DIR/images'
    import os; os.makedirs(img_dir, exist_ok=True)
    with open('$output', 'w', encoding='utf-8') as f:
        f.write('# ' + '$(basename "$input" .pptx)' + '\n\n')
        for i, slide in enumerate(prs.slides):
            f.write(f'## 第{i+1}页\n\n')
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        if para.text.strip():
                            f.write(para.text + '\n\n')
    print('OK')
except ImportError:
    print('SKIP (python-pptx not installed)')
    sys.exit(1)
except Exception as e:
    print(f'FAIL: {e}')
    sys.exit(1)
" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${YELLOW}SKIP (python-pptx 未安装)${NC}"
        return 1
    fi
}

convert_xlsx() {
    local input="$1"
    local output="$2"
    echo -n "  📈 转换 XLSX: $(basename "$input") ... "
    if python3 -c "
import sys
try:
    from openpyxl import load_workbook
    wb = load_workbook('$input', data_only=True)
    with open('$output', 'w', encoding='utf-8') as f:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            f.write(f'# {sheet_name}\n\n')
            for row in ws.iter_rows(values_only=True):
                f.write('| ' + ' | '.join(str(c) if c else '' for c in row) + ' |\n')
            f.write('\n')
    print('OK')
except ImportError:
    print('SKIP (openpyxl not installed)')
    sys.exit(1)
except Exception as e:
    print(f'FAIL: {e}')
    sys.exit(1)
" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${YELLOW}SKIP (openpyxl 未安装)${NC}"
        return 1
    fi
}

convert_pdf() {
    local input="$1"
    local output="$2"
    echo -n "  📑 转换 PDF: $(basename "$input") ... "
    echo -e "${YELLOW}SKIP (PDF转换请手动使用 pdf skill 或在支持的环境中处理)${NC}"
    echo "# $(basename "$input" .pdf)" > "$output"
    echo "" >> "$output"
    echo "> 此文件由 PDF 转换而来，请检查内容完整性。原始文件: $(basename "$input")" >> "$output"
    return 1
}

copy_markdown() {
    local input="$1"
    local output="$2"
    echo -n "  📝 复制 MD: $(basename "$input") ... "
    cp "$input" "$output"
    echo -e "${GREEN}OK${NC}"
    return 0
}

# ---------- 识别文件目标分类 ----------

classify_target() {
    local filename="$1"
    local basename=$(basename "$filename" | tr '[:upper:]' '[:lower:]')
    
    # 设备相关
    if echo "$basename" | grep -qE '设备|服务器|gpu|cpu|机器|硬件|server|device|仪器'; then
        echo "devices"
        return
    fi
    
    # 项目相关
    if echo "$basename" | grep -qE '项目|进度|需求|计划|project|proposal'; then
        echo "projects"
        return
    fi
    
    # 流程规范
    if echo "$basename" | grep -qE '规范|流程|指南|入职|离职|安全|标准|policy|guide'; then
        echo "guides"
        return
    fi
    
    # 默认知识文档
    echo "knowledge"
}

# ---------- 添加 frontmatter ----------

add_frontmatter() {
    local file="$1"
    local category="$2"
    local basename=$(basename "$file")
    local title=$(basename "$file" .md)
    local today=$(date '+%Y-%m-%d')
    
    # 检查是否已有 frontmatter
    if head -1 "$file" | grep -q '^---$'; then
        return 0
    fi
    
    # 添加 frontmatter
    local tmp="${file}.tmp"
    cat > "$tmp" << EOF
---
type: ${category}
tags: []
updated: ${today}
source: ${basename}
---

EOF
    cat "$file" >> "$tmp"
    mv "$tmp" "$file"
}

# ---------- 主处理流程 ----------

echo "📁 扫描 raw-docs/ ..."

if [ ! -d "$RAW_DIR" ] || [ -z "$(ls -A "$RAW_DIR" 2>/dev/null)" ]; then
    echo -e "${YELLOW}⚠️  raw-docs/ 目录为空，无需处理${NC}"
    exit 0
fi

for file in "$RAW_DIR"/*; do
    [ -f "$file" ] || continue
    
    filename=$(basename "$file")
    extension="${filename##*.}"
    extension=$(echo "$extension" | tr '[:upper:]' '[:lower:]')
    basename_noext="${filename%.*}"
    
    echo ""
    echo "━━━ 处理: $filename ━━━"
    
    # 确定目标分类
    category=$(classify_target "$filename")
    target_dir="$CONTEXT_DIR/$category"
    mkdir -p "$target_dir"
    
    output_file="$target_dir/${basename_noext}.md"
    
    # 检查是否已存在
    if [ -f "$output_file" ]; then
        echo -n "  ⚠️  目标文件已存在，覆盖？[y/N] "
        # 非交互模式下自动覆盖（可以通过环境变量控制）
        if [ "${LABQA_AUTO_OVERWRITE:-0}" = "1" ]; then
            echo "y (自动)"
        else
            # 默认跳过已存在的文件
            echo -e "${YELLOW}跳过 (已存在)${NC}"
            SKIP_COUNT=$((SKIP_COUNT + 1))
            continue
        fi
    fi
    
    # 根据扩展名选择转换器
    success=false
    case "$extension" in
        docx)
            convert_docx "$file" "$output_file" && success=true
            ;;
        pptx)
            convert_pptx "$file" "$output_file" && success=true
            ;;
        xlsx)
            convert_xlsx "$file" "$output_file" && success=true
            ;;
        pdf)
            convert_pdf "$file" "$output_file" && success=true
            ;;
        md)
            copy_markdown "$file" "$output_file" && success=true
            ;;
        *)
            echo -e "  ${YELLOW}⚠️  不支持的文件格式: .$extension${NC}"
            SKIP_COUNT=$((SKIP_COUNT + 1))
            continue
            ;;
    esac
    
    if $success; then
        # 添加 frontmatter
        add_frontmatter "$output_file" "$category"
        
        if [ -f "$output_file" ]; then
            NEW_COUNT=$((NEW_COUNT + 1))
            echo -e "  ${GREEN}✅ 已输出到: $output_file${NC}"
        fi
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

# ---------- 清理临时文件 ----------
rm -rf "$TEMP_DIR"

# ---------- 汇总报告 ----------
echo ""
echo "=========================================="
echo "  📊 更新汇总"
echo "=========================================="
echo -e "  ${GREEN}✅ 新转换: $NEW_COUNT 个文件${NC}"
echo -e "  ${YELLOW}⏭️  已跳过: $SKIP_COUNT 个文件${NC}"
echo -e "  ${RED}❌ 失败: $FAIL_COUNT 个文件${NC}"
echo ""

if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "${YELLOW}💡 提示: 部分文件转换失败，请检查是否安装了必要的Python库:${NC}"
    echo "   pip install python-docx python-pptx openpyxl"
fi

echo "📝 请检查 $CONTEXT_DIR 下的转换结果，确保内容正确。"
echo "   然后更新 context/navigation.md 以反映最新状态。"
