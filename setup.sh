#!/data/data/com.termux/files/usr/bin/bash

echo "╔═══════════════════════════════════════╗"
echo "║   Discord Token Hunter Bot - Setup    ║"
echo "║        สำหรับ Termux/Android          ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}[*] อัปเดตแพ็กเกจ...${NC}"
pkg update -y && pkg upgrade -y

echo -e "${YELLOW}[*] ติดตั้ง dependencies...${NC}"
pkg install -y python python-pip git

echo -e "${YELLOW}[*] ติดตั้ง Python packages...${NC}"
pip install -r requirements.txt

echo -e "${YELLOW}[*] ตั้งค่า Telegram Bot Token...${NC}"
echo ""
echo -e "ไปที่ ${GREEN}@BotFather${NC} บน Telegram"
echo "สร้างบอทใหม่ด้วย /newbot"
echo "แล้วใส่ token ที่ได้"
echo ""
read -p "ใส่ Bot Token: " bot_token

# Update config
sed -i "s/YOUR_BOT_TOKEN_HERE/$bot_token/" config.py

echo ""
echo -e "${GREEN}✅ ติดตั้งเสร็จสมบูรณ์!${NC}"
echo ""
echo -e "📌 วิธีใช้:"
echo -e "   ${YELLOW}python telegram_bot.py${NC}"
echo ""
echo -e "📱 เริ่มบอทแล้วพิมพ์ /start ใน Telegram"
echo ""

# Ask for root
read -p "ต้องการ root สำหรับ Full Scan หรือไม่? (s/N): " root_choice
if [[ "$root_choice" == "s" || "$root_choice" == "S" ]]; then
    echo -e "${YELLOW}[*] ติดตั้ง tsu...${NC}"
    pkg install -y tsu
    echo ""
    echo -e "วิธีใช้แบบ root: ${GREEN}tsu python telegram_bot.py${NC}"
fi

echo ""
echo -e "${GREEN}Happy Hacking! 🚀${NC}"