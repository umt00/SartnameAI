#!/bin/bash
# SartnameAI Azure Başlangıç Scripti

echo "Pipeline sunucusu başlatılıyor..."
python pipeline/mcp_server.py &

echo "Generator sunucusu başlatılıyor..."
python generator/mcp_server.py &

echo "Matcher sunucusu başlatılıyor..."
python matcher/mcp_server.py &

echo "Tüm FastMCP modülleri arka planda çalışıyor."
echo "Portlar: 8001 (Pipeline), 8002 (Generator), 8003 (Matcher)"

# Herhangi bir sürecin kapanmasını bekle ve onun çıkış koduyla çık
wait -n
exit $?
