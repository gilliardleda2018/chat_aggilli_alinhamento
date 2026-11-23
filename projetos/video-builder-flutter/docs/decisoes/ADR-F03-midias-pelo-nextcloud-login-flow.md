# ADR-F03: Navegar e enviar mídias direto no Nextcloud (Login Flow v2)

- Situação: Aceito
- Data: 2026-11-21

## Contexto

O servidor do Video Builder não tem ferramenta de listar pastas: no claude.ai isso é feito pelo MCP do Nextcloud
(`nc_files_list`). O app precisa mostrar as pastas, escolher clipes, fotos, músicas e legendas, e enviar arquivos
do celular (substituto da aba Download, ver ADR-F04).

## Alternativas

1. Nova ferramenta `vb_files_list` no servidor: mudança em produção. Adiada (ótima candidata para a próxima versão
   do servidor, porque evitaria o segundo login).
2. **Falar com o Nextcloud direto por WebDAV**, com senha de app obtida pelo **Login Flow v2**, o mesmo usado pelos
   apps oficiais do Nextcloud. Escolhida.

## Decisão

- `POST <nextcloud>/index.php/login/v2` → abre o link de login no navegador → o app consulta o `poll.endpoint` a cada
  2 s (até 20 min) → recebe `server`, `loginName`, `appPassword`.
- A senha de app fica no cofre do aparelho. Ela pode ser revogada a qualquer momento em
  Nextcloud → Configurações → Segurança → Dispositivos e sessões.
- Listar: `PROPFIND` (Depth 1) em `/remote.php/dav/files/<usuário>/<pasta>`.
- Enviar: `PUT` no mesmo endereço; se o arquivo existir, o app acrescenta " (2)", " (3)"... (nunca sobrescreve,
  mesma regra do servidor).
- Os caminhos guardados no roteiro são relativos à raiz do usuário (ex.: `Girona Espanha/Veneza/x.mp4`), exatamente
  o formato que `vb_media_probe` e `Clip.source` esperam.

## Consequências

- Dois logins na primeira vez (servidor e Nextcloud). Ambos ficam salvos.
- O endereço do Nextcloud é configurável (multiusuário: cada pessoa com a sua nuvem).
