# Deploy inicial na VPS Hostinger

## 1. Base recomendada

Use Ubuntu LTS limpo. Crie um usuário com `sudo`, registre a chave SSH e atualize o sistema:

```bash
sudo apt update && sudo apt upgrade -y
sudo adduser deploy
sudo usermod -aG sudo deploy
```

Valide o acesso como `deploy` antes de alterar o SSH.

## 2. Firewall

Exemplo com UFW:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from SEU_IP_FIXO to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
```

Sem IP fixo, mantenha o SSH aberto temporariamente e use proteção contra brute force. Nunca abra 5432, 8000, 5173 ou 4321.

## 3. Docker

Instale Docker Engine e o plugin Compose pelo repositório oficial do Docker. Adicione o usuário `deploy` ao grupo Docker somente se aceitar que esse grupo equivale a acesso administrativo ao host.

## 4. Projeto

```bash
git clone URL_DO_REPOSITORIO nexus
cd nexus
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production
```

Gere senhas longas e diferentes. Não reutilize a senha do painel da Hostinger.

## 5. DNS

Aponte `empresa.com.br` e `app.empresa.com.br` para o IP da VPS. Depois execute:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml ps
```

## 6. Pós-deploy

- confirme HTTPS e os health checks;
- habilite backup externo;
- configure alertas;
- configure proteção DDoS/WAF/rate limiting na borda;
- bloqueie o IP de origem para aceitar somente a camada de borda depois de testar DNS e renovação de certificados;
- teste rollback e restauração antes de liberar usuários.
