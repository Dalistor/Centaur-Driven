#!/bin/sh
# Instala ou atualiza o Centaur CLI a partir da release pública do GitHub.
#
#   curl -fsSL https://raw.githubusercontent.com/Dalistor/Centaur-Driven/main/install.sh | sh
#
# Variáveis opcionais:
#   CENTAUR_VERSION=0.10.8        instala uma versão específica (padrão: a release mais recente)
#   CENTAUR_EXTRAS=attachments    extras do pacote, separados por vírgula (attachments, computer)
#   CENTAUR_INSTALLER=pipx        força uv ou pipx (padrão: uv quando instalado, senão pipx)
#
# O wheel é conferido contra o SHA256SUMS da release e instalado em um ambiente isolado
# com uv ou pipx; nada é instalado com sudo nem no Python do sistema.
set -eu

REPO="Dalistor/Centaur-Driven"
BASE="https://github.com/$REPO/releases"

fail() {
    printf 'Erro: %s\n' "$1" >&2
    exit 1
}

command -v curl >/dev/null 2>&1 || fail 'curl não encontrado; instale-o e tente de novo.'

case "$(uname -s)" in
    Linux|Darwin) ;;
    *) fail 'o Centaur CLI roda em Linux e macOS (no Windows, use o WSL).' ;;
esac

installer="${CENTAUR_INSTALLER:-}"
if [ -n "$installer" ]; then
    case "$installer" in
        uv|pipx) command -v "$installer" >/dev/null 2>&1 || fail "$installer não encontrado." ;;
        *) fail 'CENTAUR_INSTALLER deve ser uv ou pipx.' ;;
    esac
elif command -v uv >/dev/null 2>&1; then
    installer=uv
elif command -v pipx >/dev/null 2>&1; then
    installer=pipx
else
    fail 'instale o uv (https://docs.astral.sh/uv/getting-started/installation/) ou o pipx (https://pipx.pypa.io) e execute este script de novo.'
fi

version="${CENTAUR_VERSION:-}"
if [ -z "$version" ]; then
    latest=$(curl -fsSLI -o /dev/null -w '%{url_effective}' "$BASE/latest") \
        || fail 'não foi possível consultar a release mais recente no GitHub.'
    case "$latest" in
        */tag/cli-v*) version="${latest##*/tag/cli-v}" ;;
        *) fail 'a release mais recente não é do Centaur CLI; informe CENTAUR_VERSION=<versão>.' ;;
    esac
fi
case "$version" in
    ''|*[!0-9A-Za-z.]*) fail "versão inválida: $version" ;;
esac

extras="${CENTAUR_EXTRAS:-}"
case "$extras" in
    *[!a-z,]*) fail 'CENTAUR_EXTRAS aceita nomes separados por vírgula, como attachments,computer.' ;;
esac

wheel="centaur_cli-$version-py3-none-any.whl"
directory=$(mktemp -d)
trap 'rm -rf "$directory"' EXIT INT TERM

printf 'Baixando o Centaur CLI %s…\n' "$version"
curl -fsSL -o "$directory/$wheel" "$BASE/download/cli-v$version/$wheel" \
    || fail "a release cli-v$version não tem o pacote $wheel."
curl -fsSL -o "$directory/SHA256SUMS" "$BASE/download/cli-v$version/SHA256SUMS" \
    || fail "a release cli-v$version não tem SHA256SUMS."

expected=$(awk -v name="$wheel" '{ file = $2; sub(/^.*\//, "", file); if (file == name) print $1 }' "$directory/SHA256SUMS")
[ -n "$expected" ] || fail 'o SHA256SUMS da release não lista o pacote baixado.'
if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$directory/$wheel" | awk '{ print $1 }')
elif command -v shasum >/dev/null 2>&1; then
    actual=$(shasum -a 256 "$directory/$wheel" | awk '{ print $1 }')
else
    fail 'sha256sum ou shasum não encontrado; não é possível conferir o pacote.'
fi
[ "$actual" = "$expected" ] || fail 'o pacote baixado não confere com o SHA256SUMS da release; nada foi instalado.'

requirement="centaur-cli${extras:+[$extras]} @ file://$directory/$wheel"
printf 'Instalando com %s…\n' "$installer"
if [ "$installer" = uv ]; then
    uv tool install --force --python '>=3.10' "$requirement"
else
    pipx install --force "$requirement"
fi

found=$(command -v centaur 2>/dev/null || true)
if [ -n "$found" ] && [ "$(centaur --version 2>/dev/null)" = "centaur $version" ]; then
    printf '\nPronto: centaur %s\nAbra um projeto com: centaur /caminho/do/projeto\n' "$version"
elif [ -n "$found" ]; then
    printf '\nInstalado, mas o "centaur" encontrado primeiro no PATH é outra instalação (%s). Remova-a ou ajuste o PATH.\n' "$found"
elif [ "$installer" = uv ]; then
    printf '\nInstalado, mas "centaur" ainda não está no PATH. Execute "uv tool update-shell" e reabra o terminal.\n'
else
    printf '\nInstalado, mas "centaur" ainda não está no PATH. Execute "pipx ensurepath" e reabra o terminal.\n'
fi
