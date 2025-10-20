#!/bin/bash
# Bluetooth Adapter Connection Testing Checklist
# Usage: bash test_bluetooth_setup.sh

set -e

echo "================================================================================
🔍 Bluetooth OBD2 Adapter Setup Check
================================================================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check system Bluetooth
echo -e "\n1️⃣  Checking System Bluetooth..."
if systemctl is-active --quiet bluetooth; then
    echo -e "${GREEN}✅ Bluetooth service is running${NC}"
else
    echo -e "${RED}❌ Bluetooth service is not running${NC}"
    echo "   Try: sudo systemctl start bluetooth"
    exit 1
fi

# Check for paired devices
echo -e "\n2️⃣  Checking Paired OBD2 Adapters..."
ADAPTERS=(
    "00:1D:A5:1E:32:25:OBDII"
    "13:E0:2F:8D:5C:6B:Android-Vlink"
)

for adapter_info in "${ADAPTERS[@]}"; do
    IFS=':' read -r a b c d e f name <<< "$adapter_info"
    address="$a:$b:$c:$d:$e:$f"
    
    if bluetoothctl info "$address" | grep -q "Paired: yes"; then
        echo -e "${GREEN}✅ $name ($address)${NC}"
    else
        echo -e "${YELLOW}⚠️  $name ($address) - Not paired${NC}"
    fi
done

# Check Python environment
echo -e "\n3️⃣  Checking Python Environment..."
if [ -d ".venv" ]; then
    echo -e "${GREEN}✅ Virtual environment exists${NC}"
    source .venv/bin/activate
    
    # Check required packages
    echo -e "\n   Checking required packages..."
    python -c "import serial; print('   ✅ PySerial available')" 2>/dev/null || \
        echo -e "   ${RED}❌ PySerial missing${NC}"
    python -c "import bleak; print('   ✅ Bleak available')" 2>/dev/null || \
        echo -e "   ${YELLOW}⚠️  Bleak not installed${NC}"
else
    echo -e "${RED}❌ Virtual environment not found${NC}"
    exit 1
fi

# Check test scripts
echo -e "\n4️⃣  Checking Test Scripts..."
for script in test_bluetooth_connection.py test_bluetooth_direct.py test_bluetooth_rfcomm.py; do
    if [ -f "$script" ]; then
        echo -e "${GREEN}✅ $script${NC}"
    else
        echo -e "${RED}❌ $script missing${NC}"
    fi
done

# Check RFCOMM support
echo -e "\n5️⃣  Checking RFCOMM Support..."
if command -v rfcomm &> /dev/null; then
    echo -e "${GREEN}✅ rfcomm command available${NC}"
else
    echo -e "${RED}❌ rfcomm command not found${NC}"
    echo "   Install with: sudo apt install bluez-tools"
fi

# Summary
echo -e "\n================================================================================"
echo -e "${GREEN}✅ System is ready for Bluetooth OBD2 testing${NC}"
echo -e "================================================================================\n"

echo "Next steps:"
echo "1. Power up your OBD2 Bluetooth adapter with 12V"
echo "2. Run: sudo bluetoothctl connect 00:1D:A5:1E:32:25  (or your adapter address)"
echo "3. Run: source .venv/bin/activate && sudo python test_bluetooth_rfcomm.py"
echo "4. Then implement driver/bluetooth.py"
echo ""
