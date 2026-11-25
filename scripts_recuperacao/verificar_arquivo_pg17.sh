#!/bin/sh
# Qualquer NOME de arquivo; exige conteudo fisico PG17 e caminhos seguros.
set -eu
[ -s /backup/input.tar.gz ] || exit 71
list=/tmp/arquivos_pg17.txt
tar -tzf /backup/input.tar.gz > "$list" 2>/dev/null || exit 72
if grep -Eq '^/|(^|/)\.\.(/|$)' "$list"; then exit 73; fi
grep -Eq '^\./PG_VERSION$|^PG_VERSION$' "$list" || exit 74
grep -Eq '^\./global/pg_control$|^global/pg_control$' "$list" || exit 75
grep -Eq '^\./base/|^base/' "$list" || exit 76
version="$(tar -xOzf /backup/input.tar.gz ./PG_VERSION 2>/dev/null || tar -xOzf /backup/input.tar.gz PG_VERSION 2>/dev/null || :)"
[ "$version" = 17 ] || exit 77
printf '%s\n' BACKUP_PG17_COMPATIVEL=OK
