import os
import json
import time
import shutil

TASKS_DIR = './output/tasks'
TASKS_INDEX = os.path.join(TASKS_DIR, '_tasks_index.json')


class TaskManager:
    def __init__(self):
        os.makedirs(TASKS_DIR, exist_ok=True)
        self.tasks = self._load_index()
        # 回收站
        self.trash_dir = os.path.join(os.path.dirname(TASKS_DIR), "tasks_trash")
        os.makedirs(self.trash_dir, exist_ok=True)

    def _load_index(self):
        if os.path.exists(TASKS_INDEX):
            with open(TASKS_INDEX, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save_index(self):
        with open(TASKS_INDEX, 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)

    def create_task(self, name):
        safe_name = name.strip().replace(' ', '_').replace('/', '_').replace('\\', '_')
        if not safe_name:
            safe_name = 'task_' + str(int(time.time()))
        for t in self.tasks:
            if t['name'] == safe_name:
                return None  # 任务名重复，由调用方处理提示
                break
        task_dir = os.path.join(TASKS_DIR, safe_name)
        os.makedirs(task_dir, exist_ok=True)
        for sub in ['scripts', 'images', 'videos', 'audio', 'final', 'state', 'profiles', 'characters', 'backgrounds']:
            os.makedirs(os.path.join(task_dir, sub), exist_ok=True)
        task = {
            'name': safe_name,
            'display_name': name.strip(),
            'dir': task_dir,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'novel_path': None,
            'total_episodes': 0,
            'current_step': 0,
            'status': 'new',
        }
        self.tasks.append(task)
        self._save_index()
        return task

    def delete_task(self, name):
        """Delete task - move to trash instead of permanent delete"""
        task = self.get_task(name)
        if not task:
            return False
        
        task_dir = task.get('dir', '')
        if task_dir and os.path.exists(task_dir):
            # Move to trash
            import time
            trash_name = f"{name}_{int(time.time())}"
            trash_path = os.path.join(self.trash_dir, trash_name)
            try:
                shutil.move(task_dir, trash_path)
                # Save trash metadata
                meta = {
                    'original_name': name,
                    'display_name': task.get('display_name', name),
                    'deleted_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'original_task': task,
                    'trash_path': trash_path
                }
                meta_file = os.path.join(trash_path, '_trash_meta.json')
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
                print(f"[TaskManager] moved to trash: {trash_path}")
            except Exception as e:
                print(f"[TaskManager] move to trash failed: {e}, trying permanent delete")
                shutil.rmtree(task_dir, ignore_errors=True)
        
        # Remove from index
        self.tasks = [t for t in self.tasks if t.get('name') != name]
        self._save_index()
        return True

    def list_trash(self):
        """List all trashed tasks"""
        result = []
        if not os.path.exists(self.trash_dir):
            return result
        for d in os.listdir(self.trash_dir):
            full = os.path.join(self.trash_dir, d)
            if os.path.isdir(full):
                meta_file = os.path.join(full, '_trash_meta.json')
                if os.path.exists(meta_file):
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    meta['trash_dir_name'] = d
                    result.append(meta)
                else:
                    result.append({
                        'original_name': d.rsplit('_', 1)[0] if '_' in d else d,
                        'display_name': d.rsplit('_', 1)[0] if '_' in d else d,
                        'deleted_at': 'unknown',
                        'trash_dir_name': d,
                        'trash_path': full
                    })
        return result

    def restore_task(self, trash_dir_name):
        """Restore a task from trash"""
        trash_path = os.path.join(self.trash_dir, trash_dir_name)
        if not os.path.exists(trash_path):
            return False, "trash not found"
        
        # Read meta
        meta_file = os.path.join(trash_path, '_trash_meta.json')
        if os.path.exists(meta_file):
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            original_task = meta.get('original_task', {})
            name = meta.get('original_name', trash_dir_name)
            display_name = meta.get('display_name', name)
        else:
            name = trash_dir_name.rsplit('_', 1)[0] if '_' in trash_dir_name else trash_dir_name
            display_name = name
            original_task = {}
        
        # Check if name already exists
        if self.get_task(name):
            return False, f"task '{name}' already exists"
        
        # Move back
        restore_dir = os.path.join(TASKS_DIR, name)
        try:
            shutil.move(trash_path, restore_dir)
        except Exception as e:
            return False, str(e)
        
        # Remove trash meta
        meta_in_restore = os.path.join(restore_dir, '_trash_meta.json')
        if os.path.exists(meta_in_restore):
            os.remove(meta_in_restore)
        
        # Re-add to index
        task_info = original_task if original_task else {
            'name': name,
            'display_name': display_name,
            'dir': restore_dir,
        }
        task_info['dir'] = restore_dir
        self.tasks.append(task_info)
        self._save_index()
        
        return True, f"restored: {display_name}"

    def empty_trash(self):
        """Permanently delete all trashed tasks"""
        if os.path.exists(self.trash_dir):
            shutil.rmtree(self.trash_dir)
            os.makedirs(self.trash_dir, exist_ok=True)
        return True

    def get_task(self, name):
        for t in self.tasks:
            if t['name'] == name:
                return t
        return None

    def update_task(self, name, **kwargs):
        for t in self.tasks:
            if t['name'] == name:
                t.update(kwargs)
                break
        self._save_index()

    def list_tasks(self):
        return list(self.tasks)

    def get_task_dirs(self, task_name):
        task_dir = os.path.join(TASKS_DIR, task_name)
        return {
            'base': task_dir,
            'scripts': os.path.join(task_dir, 'scripts'),
            'images': os.path.join(task_dir, 'images'),
            'videos': os.path.join(task_dir, 'videos'),
            'audio': os.path.join(task_dir, 'audio'),
            'final': os.path.join(task_dir, 'final'),
            'state': os.path.join(task_dir, 'state'),
            'profiles': os.path.join(task_dir, 'profiles'),
            'characters': os.path.join(task_dir, 'characters'),
            'backgrounds': os.path.join(task_dir, 'backgrounds'),

        }
