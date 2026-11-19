# Read with: source ./setup.sh
if [[ -n "${BASH_VERSION:-}" ]]; then
    if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
        printf 'source ./setup.sh で読み込んでください。\n' >&2
        exit 1
    fi
    _server_knocks_setup_file="${BASH_SOURCE[0]}"
elif [[ -n "${ZSH_VERSION:-}" ]]; then
    _server_knocks_setup_file="${(%):-%x}"
else
    printf 'Bashまたはzshで source ./setup.sh を実行してください。\n' >&2
    return 1
fi
SERVER_KNOCKS_DIR="$(cd "$(dirname "$_server_knocks_setup_file")" && pwd -P)"
unset _server_knocks_setup_file
server-check() {
    python3 "$SERVER_KNOCKS_DIR/server-check" "$@"
}
printf 'server-check を登録しました。判定と進捗確認はサーバのログインノードで実行してください。\n'
