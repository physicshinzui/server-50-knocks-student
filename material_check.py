"""Check student answers, course artifacts, and read-only PBS status."""
import csv
import getpass
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tarfile

SAMPLE = 'data/original/samples.tsv'
UPLOADED = 'work/my-samples.csv'
MISSING = 'data/original/missing.tsv'
JOB_ID = re.compile(r'[0-9]+\.[a-zA-Z0-9_.-]+')


class CheckError(Exception):
    pass


def need(condition, message):
    if not condition:
        raise CheckError(message)


def answer(prompt, expected, *aliases):
    value = input(prompt + ': ').strip()
    need(value in (str(expected), *aliases), '記録やコマンドの表示を確かめてください。')


def read(root, name):
    path = root / name
    need(root in path.resolve().parents, '教材内のファイルを使ってください。')
    need(path.is_file() and path.stat().st_size <= 1_000_000, name + ' を確認してください。')
    return path.read_bytes()


def lines(root, name):
    return read(root, name).decode('utf-8').splitlines()


def submitted_id(prompt='qsubが表示したジョブID'):
    job_id = input(prompt + 'を入力してください: ').strip()
    need(JOB_ID.fullmatch(job_id), '番号とサーバ名を含むジョブIDを入力してください。')
    return job_id


def pbs_status(job_id):
    process = subprocess.run(['qstat', '-f', job_id], capture_output=True, text=True,
                             timeout=10, env={**os.environ, 'LC_ALL': 'C'})
    if process.returncode:
        if re.search(r'Unknown Job Id\b', process.stderr, re.I) and job_id in process.stderr:
            return None
        raise CheckError('PBSに照会できません。同じIDをqstatで確認してください。')
    return dict(re.findall(r'^\s*(\S+)\s+=\s+(.+)$', process.stdout, re.M))


def log_fields(root, job_id):
    entries = lines(root, f'work/runs/{job_id}/run.log')
    fields = dict(line.split('=', 1) for line in entries if re.match(r'^[a-z_]+=', line))
    need(fields.get('job_id') == job_id and fields.get('host') not in ('', None, socket.gethostname()),
         '今回の計算ノードで作られたログを確認してください。')
    return fields


def script_settings(root, path, cpu=None, memory=None, walltime=None):
    script = lines(root, path)
    directives = ' '.join(line.lstrip()[4:] for line in script if line.lstrip().startswith('#PBS '))
    for key, value in {'ncpus': cpu, 'mem': memory, 'walltime': walltime}.items():
        if value is not None:
            need(re.search(r'(?:^|[\s:])'+key+'='+re.escape(str(value))+r'(?=[:\s]|$)', directives),
                 f'#PBS行の {key} を確認してください。')
    return script, directives


def has_pbs_option(script, option):
    target = ' '.join(option.split())
    return any(' '.join(line.split()) == target for line in script if line.lstrip().startswith('#PBS '))


def has_command(script, command):
    target = ' '.join(command.split())
    return any(' '.join(line.split('#', 1)[0].split()) == target for line in script)


def table_rows(root, name):
    is_csv = Path(name).suffix.lower() == '.csv'
    delimiter = ',' if is_csv else '\t'
    reader = csv.DictReader(io.StringIO(read(root, name).decode()), delimiter=delimiter)
    separator = 'カンマ' if is_csv else 'タブ'
    need(reader.fieldnames == ['sample_id', 'group', 'value'], f'列名と{separator}区切りを確認してください。')
    rows = list(reader)
    need(len(rows) >= 2 and all(row.get('sample_id') and row.get('group') and
                                row.get('value') and None not in row for row in rows),
         '試料名・群・整数の値を持つ行を2行以上用意してください。')
    for row in rows:
        need(re.fullmatch(r'[+-]?[0-9]+', row['value']), 'value列には整数を指定してください。')
    return rows


def result(root, job_id, input_name):
    fields = log_fields(root, job_id)
    need(fields.get('status') == 'OK' and fields.get('input') == input_name,
         '同じジョブのログで入力ファイルと終了状態を確認してください。')
    values = [int(row['value']) for row in table_rows(root, input_name)]
    expected = {'count': len(values), 'sum': sum(values), 'mean': sum(values)/len(values)}
    report = json.loads(read(root, f'work/runs/{job_id}/result.json'))
    need(report == expected, '集計結果が入力と一致するか確かめてください。')
    return fields, report


def owned_job(fields, name):
    return (fields.get('Job_Name') == name and
            fields.get('Job_Owner', '').split('@')[0] == getpass.getuser())


def check_submission(root, job_id, name, label):
    path = root / 'work' / 'runs' / job_id / 'run.log'
    if path.is_file():
        need(log_fields(root, job_id).get('lesson') == label, 'この問題で投入したジョブIDを使ってください。')
    else:
        fields = pbs_status(job_id)
        need(fields and owned_job(fields, name),
             'この問題のジョブが見つかりません。IDとPBSの出力を確認してください。')


def conda_env(name):
    conda = os.environ.get('CONDA_EXE')
    need(conda and Path(conda).is_file(), 'Miniforgeの設定を読み込んでください。')
    response = subprocess.run([conda, 'env', 'list', '--json'], capture_output=True, text=True, timeout=20)
    need(response.returncode == 0, 'conda env list が実行できることを確認してください。')
    matches = [Path(path) for path in json.loads(response.stdout)['envs'] if Path(path).name == name]
    need(matches, f'環境 {name} を用意してください。')
    return matches[0]


def active_env(name):
    need(os.environ.get('CONDA_DEFAULT_ENV') == name and Path(sys.prefix).name == name,
         f'{name} を有効にした端末で判定してください。')
    need(sys.version_info[:2] == (3, 11), '環境のPythonは3.11を使ってください。')


def numpy_version():
    try:
        return importlib.metadata.version('numpy')
    except importlib.metadata.PackageNotFoundError:
        raise CheckError('有効にした環境にNumPyを導入してください。')


def check_archive(root, job_id):
    prefix = f'work/runs/{job_id}/'
    expected = {prefix + name for name in ('run.log', 'result.json')}
    try:
        with tarfile.open(fileobj=io.BytesIO(read(root, 'work/my-results.tar.gz')), mode='r:gz') as archive:
            found = set()
            for member in archive:
                if member.isdir():
                    continue
                need(member.isfile() and member.name in expected - found and member.size <= 1_000_000,
                     '指定の実行ディレクトリだけを収録してください。')
                need(archive.extractfile(member).read() == read(root, member.name),
                     'アーカイブ内の内容を元の実行結果と照合してください。')
                found.add(member.name)
            need(found == expected, 'ログと結果を両方収録してください。')
    except (tarfile.TarError, EOFError) as error:
        raise CheckError('gzip圧縮したtarアーカイブを作成してください。') from error


def validate(number, root, progress):
    root = root.resolve()

    def saved_job(previous):
        job_id = progress.get(f'{previous:03d}', {}).get('job_id', '')
        need(isinstance(job_id, str) and JOB_ID.fullmatch(job_id), f'先に server-check {previous:03d} でジョブIDを確認してください。')
        return job_id

    config = json.loads(read(root, 'course_config.json'))
    queue = config['cpu_queue']
    gpu_queue = config['gpu_queue']
    if number == 1:
        need(Path.cwd().resolve() == root, 'SSHで接続し、教材の最上位に移動してください。')
    elif number == 2:
        need(Path.cwd().resolve() == root, '教材の最上位で現在地を確認してください。')
        answer('接続先のホスト名', socket.gethostname())
    elif number == 3:
        script, directives = script_settings(root, 'work/first.sh', 1, '256mb', '00:03:00')
        need('ngpus=0' in directives and has_pbs_option(script, f'#PBS -q {queue}'), 'GPU数とキューを確認してください。')
        need(has_command(script, f'bash tools/run_lesson.sh first {SAMPLE}'), '配布済みの入力を使ってください。')
    elif number in (4, 8, 11, 16, 32, 39, 42, 43, 44, 46, 48, 55):
        prompt = {42: 'work/gpu.sh のジョブID', 43: 'templates/bad_cmd.sh のジョブID',
                  44: '計算ノードで控えたジョブID', 48: '取消に使ったジョブID',
                  55: 'work/path_job.sh のジョブID'}
        job_id = submitted_id(prompt[number]) if number in prompt else submitted_id()
        if number in (4, 8, 11, 16, 32, 39):
            name, label = {4: ('s50first', 'first'), 8: ('s50retry', 'retry'),
                           11: ('s50retry', 'retry'), 16: ('s50mydata', 'my-data'),
                           32: ('s50python', 'python'), 39: ('s50resources', 'resources')}[number]
            if number == 11:
                need(job_id != saved_job(8), '修正後に投入した新しいジョブIDを入力してください。')
            check_submission(root, job_id, name, label)
        elif number == 42:
            script, directives = script_settings(root, 'work/gpu.sh')
            need(re.search(r'(?:^|[\s:])ngpus=1(?=[:\s]|$)', directives) and
                 has_pbs_option(script, f'#PBS -q {gpu_queue}'),
                 f'#PBS行で ngpus=1 とキュー {gpu_queue} を指定してください。')
            fields = log_fields(root, job_id)
            need(fields.get('lesson') == 'gpu' and fields.get('status') == 'OK' and fields.get('gpu'),
                 'GPUジョブが正常終了したログ（nvidia-smiの結果）を確認してください。')
            answer('ログに表示された gpu の値（GPUモデル名）', fields['gpu'])
        elif number == 43:
            numeric_id = job_id.split('.', 1)[0]
            need(not (root / 'work' / 'runs' / job_id / 'run.log').exists(),
                 'run.log が作られる前に終了したジョブのIDを入力してください。')
            pbs_out = read(root, f's50badcmd.o{numeric_id}').decode('utf-8', errors='replace')
            need('nonexistent_tool' in pbs_out,
                 f's50badcmd.o{numeric_id} に記録されたエラーを確認してください。')
            answer('見つからなかったコマンド名', 'nonexistent_tool')
        elif number == 44:
            fields, _ = result(root, job_id, SAMPLE)
            need(fields.get('lesson') == 'interactive', '対話型ジョブで作ったログを使ってください。')
            answer('計算ノードのホスト名', fields['host'])
        elif number == 46:
            fields = pbs_status(job_id)
            need(fields and owned_job(fields, 's50cancel') and fields.get('job_state') == 'H',
                 '自分の取消練習用ジョブが保留中であることを確認してください。')
        elif number == 55:
            script = lines(root, 'work/path_job.sh')
            need(any('export PATH=' in line.split('#', 1)[0] and '$PATH' in line.split('#', 1)[0] for line in script),
                 'work/path_job.sh に export PATH="...:$PATH" を記述してください。')
            fields = log_fields(root, job_id)
            need(fields.get('lesson') == 'path' and fields.get('status') == 'OK' and
                 fields.get('output') == 'hello from mytool' and
                 fields.get('tool', '').endswith('work/bin/mytool'),
                 'work/path_job.sh が正常終了し、mytool が実行されたログを確認してください。')
            answer('ログに表示された tool の値', fields['tool'])
        else:
            need(job_id == saved_job(46), '046で確認したIDを使ってください。')
            fields = pbs_status(job_id)
            need(fields is None or (owned_job(fields, 's50cancel') and fields.get('job_state') in ('F', 'X')),
                 '取消が反映されたか、同じIDをもう一度確認してください。')
        return {'job_id': job_id}
    elif number == 5:
        saved_job(4)
        answer('待機中を示す状態コード', 'Q', 'q')
    elif number == 6:
        answer('計算ノードのホスト名', log_fields(root, saved_job(4))['host'])
    elif number == 7:
        _, report = result(root, saved_job(4), SAMPLE)
        answer('処理したデータの件数', report['count'])
    elif number == 9:
        fields = log_fields(root, saved_job(8))
        need(fields.get('input') == MISSING and fields.get('status', '').startswith('ERROR'),
             '入力エラーで終了したジョブのログを確認してください。')
        answer('見つからなかった入力のパス', MISSING)
    elif number == 10:
        need(has_command(lines(root, 'work/retry.sh'), f'bash tools/run_lesson.sh retry {SAMPLE}'),
             '実行する入力パスを確認してください。')
    elif number == 12:
        fields, _ = result(root, saved_job(11), SAMPLE)
        answer('修正後のstatusの値', fields['status'])
    elif number in (13, 14):
        message = lines(root, 'work/hello.txt')
        need(len(message) == 1 and message[0].strip(), '短い文を1行書いたhello.txtをSCPで送ってください。')
        if number == 14:
            answer('hello.txtに書かれている文', message[0].strip())
    elif number == 15:
        table_rows(root, UPLOADED)
        script = lines(root, 'work/my-data.sh')
        need(has_command(script, f'bash tools/run_lesson.sh my-data {UPLOADED}') and
             has_pbs_option(script, '#PBS -N s50mydata'),
             'ジョブ名と送った入力の指定を確認してください。')
    elif number in (17, 18):
        _, report = result(root, saved_job(16), UPLOADED)
        key = 'count' if number == 17 else 'sum'
        answer(f'結果の {key}', report[key])
    elif number in (19, 20, 21, 22):
        job_id = saved_job(16)
        check_archive(root, job_id)
        if number == 20:
            answer('ログのファイル名', 'run.log')
        elif number == 21:
            for name in ('run.log', 'result.json'):
                orig = f'work/runs/{job_id}/{name}'
                extracted = f'work/extracted/{orig}'
                need(read(root, extracted) == read(root, orig),
                     'work/extracted にアーカイブを展開し、元のファイルと一致することを確認してください。')
        elif number == 22:
            answer('アーカイブ内の実行ディレクトリのジョブID', job_id)
    elif number in (23, 25):
        need(read(root, 'work/sync/samples.csv') == read(root, UPLOADED), '送信したCSVを確認してください。')
        content = read(root, 'work/sync/README.md')
        need(content.strip(), 'データの出所をREADME.mdに書いてください。')
        digest = hashlib.sha256(content).hexdigest()
        if number == 23:
            return {'readme_hash': progress.get('023', {}).get('readme_hash', digest)}
        previous = progress.get('023', {}).get('readme_hash')
        need(previous and previous != digest, '023で初回転送を確認し、追記を同期してください。')
    elif number == 24:
        answer('ドライランで表示された変更予定のファイル名', 'README.md')
    elif number == 26:
        conda = os.environ.get('CONDA_EXE')
        need(conda and Path(conda).is_file(), 'Miniforgeの設定を読み込んでください。')
    elif number == 27:
        python = conda_env('lab-py') / 'bin/python'
        version = subprocess.run([str(python), '--version'], capture_output=True, text=True, timeout=10)
        need(version.returncode == 0 and version.stdout.startswith('Python 3.11.'), 'Python 3.11の環境を作成してください。')
    elif number == 28:
        active_env('lab-py')
        output = subprocess.run(['python', '--version'], capture_output=True, text=True, timeout=10)
        version = re.fullmatch(r'Python (3\.11\.[0-9]+)', output.stdout.strip())
        need(output.returncode == 0 and version, '有効にした環境で python --version を確認してください。')
        answer('python --version で表示されたバージョン番号', version[1], version[0])
    elif number in (29, 30, 36):
        active_env('lab-py-replay' if number == 36 else 'lab-py')
        if number in (29, 30, 36):
            version = numpy_version()
            if number == 30:
                answer('NumPyのバージョン', version)
    elif number == 31:
        script = lines(root, 'work/python.sh')
        need(any(line.split('#', 1)[0].strip().startswith('source ') and 'conda.sh' in line.split('#', 1)[0]
                 for line in script) and has_command(script, 'conda activate lab-py'),
             'ジョブ内のMiniforge初期化と環境名を確認してください。')
    elif number in (33, 34):
        fields, _ = result(root, saved_job(32), SAMPLE)
        need('lab-py' in Path(fields.get('python', '')).parts and fields.get('numpy'),
             '計算ノードのログで使用した環境とNumPyを確認してください。')
        key = 'python' if number == 33 else 'numpy'
        answer(f'ログに表示された {key} の値', fields[key])
    elif number == 35:
        dependencies = '\n'.join(lines(root, 'work/environment.yml'))
        need(re.search(r'^\s*-\s+python=3\.11(?:\s|\.|$)', dependencies, re.M) and
             re.search(r'^\s*-\s+numpy(?:[=\s]|$)', dependencies, re.M),
             'Python 3.11とNumPyが含まれる環境定義を保存してください。')
    elif number == 37:
        answer('短時間CPU用のキュー名', queue)
        answer('重い計算処理をログインノードで直接実行してよいですか（yes/no）', 'no')
    elif number == 38:
        script, _ = script_settings(root, 'work/resources.sh', cpu=2, memory='512mb', walltime='00:02:00')
        need(has_pbs_option(script, '#PBS -N s50resources') and
             has_command(script, f'bash tools/run_lesson.sh resources {SAMPLE}'),
             '実行を区別するためのジョブ名と実行名を確認してください。')
    elif number == 40:
        saved_job(39)
        answer('PBSの詳細で割当先を示す項目名', 'exec_vnode')
    elif number == 41:
        result(root, saved_job(39), SAMPLE)
        answer('CPUを2個要求するだけで並列化されますか（yes/no）', 'no')
    elif number == 45:
        failed_id = saved_job(8)
        fields = log_fields(root, failed_id)
        need(fields.get('status', '').startswith('ERROR'), '008のエラー終了ログを確認してください。')
        answer('grepで見つかったエラー終了ジョブのID', failed_id)
    elif number == 47:
        fields = pbs_status(saved_job(46))
        need(fields and owned_job(fields, 's50cancel') and fields.get('job_state') == 'H',
             '自分の練習用ジョブが保留中であることを確認してください。')
        answer('保留中を示す状態コード', 'H', 'h')
    elif number == 49:
        saved_job(48)
        answer('一覧から消えただけで正常終了と判断できますか（yes/no）', 'no')
    elif number == 50:
        usage = [line.strip() for line in lines(root, 'work/disk-usage.txt') if line.strip()]
        need(len(usage) == 1, 'du -sh work の結果を work/disk-usage.txt に保存してください。')
        match = re.fullmatch(r'(\S+)\s+(?:\./)?work/?', usage[0])
        need(match, 'du -sh work の出力形式を確認してください。')
        answer('work/disk-usage.txt に記録された work のサイズ', match.group(1))
    elif number == 51:
        qsub_path = shutil.which('qsub')
        need(qsub_path, 'qsub コマンドが見つかりません。')
        answer('which qsub で表示されたパス', qsub_path)
    elif number == 52:
        active_env('lab-py')
        py_path = shutil.which('python')
        need(py_path and 'lab-py' in Path(py_path).parts,
             'lab-py を有効にした端末で which python を確認してください。')
        answer('which python で表示されたパス', py_path)
        answer('PATHの先頭に環境のbinが追加されることでコマンドが切り替わりますか（yes/no）', 'yes')
    elif number == 53:
        mytool = root / 'work/bin/mytool'
        need(mytool.is_file() and os.access(mytool, os.X_OK),
             'work/bin/mytool を作成し、chmod +x で実行権限を付けてください。')
        out = subprocess.run([str(mytool)], capture_output=True, text=True, timeout=10)
        need(out.returncode == 0 and out.stdout.strip() == 'hello from mytool',
             'work/bin/mytool を実行すると hello from mytool と出力されるようにしてください。')
    elif number == 54:
        found = shutil.which('mytool')
        need(found and Path(found).resolve() == (root / 'work/bin/mytool').resolve(),
             'export PATH="$PWD/work/bin:$PATH" を実行した端末で判定してください。')
        need(shutil.which('ls'), '$PATH を上書きせず、末尾に :$PATH を残してください。')
    else:
        raise ValueError('unknown question')
    return {}
