import { Box, Menu } from '@mantine/core';
import {
  IconClipboard, IconCopy, IconDownload, IconFileText, IconFolder, IconFolderPlus,
  IconPencil, IconRefresh, IconScissors, IconTrash, IconUpload,
} from '@tabler/icons-react';
import { baseName } from './format';
import type { FileBrowser } from './useFileBrowser';

/**
 * 右键菜单：一个受控的浮层菜单，用 1px 的虚拟目标钉在右键位置上
 * （Mantine 的 Menu.position 只收浮动方位，不收坐标）。
 */
export function FileMenu({ browser }: { browser: FileBrowser }) {
  const { menu, menuItems, menuTarget } = browser;
  const where = baseName(menuTarget);
  const entry = menu?.entry;

  return (
    <Menu
      opened={!!menu}
      onChange={(open) => {
        if (!open) browser.closeMenu();
      }}
      position="bottom-start"
      offset={0}
      shadow="md"
      withinPortal
    >
      <Menu.Target>
        <Box
          style={{
            position: 'fixed',
            top: menu?.y ?? 0,
            left: menu?.x ?? 0,
            width: 1,
            height: 1,
            pointerEvents: 'none',
          }}
        />
      </Menu.Target>
      <Menu.Dropdown>
        {entry && (
          <>
            <Menu.Item
              leftSection={<IconFolder size={14} />}
              onClick={() => (entry.dir ? browser.navigate(entry.path) : void browser.openEntry(entry))}
            >
              {entry.dir ? '打开' : '下载并用默认程序打开'}
            </Menu.Item>
            {!entry.dir && (
              <>
                <Menu.Item leftSection={<IconFileText size={14} />} onClick={() => browser.setPreview(entry)}>
                  预览文本
                </Menu.Item>
                <Menu.Item
                  leftSection={<IconDownload size={14} />}
                  onClick={() => void browser.download(menuItems)}
                >
                  下载到…（{menuItems.length} 项）
                </Menu.Item>
              </>
            )}
            <Menu.Divider />
            <Menu.Item
              leftSection={<IconCopy size={14} />}
              disabled={!menuItems.length}
              onClick={() => void browser.copy('copy')}
            >
              复制{menuItems.length > 1 ? `（${menuItems.length} 项）` : ''}
            </Menu.Item>
            <Menu.Item
              leftSection={<IconScissors size={14} />}
              disabled={!menuItems.length}
              onClick={() => void browser.copy('move')}
            >
              剪切{menuItems.length > 1 ? `（${menuItems.length} 项）` : ''}
            </Menu.Item>
            <Menu.Item
              leftSection={<IconClipboard size={14} />}
              disabled={!browser.clipboard}
              onClick={() => void browser.pasteInto(menuTarget)}
            >
              粘贴到 {where}
            </Menu.Item>
            <Menu.Divider />
            <Menu.Item
              leftSection={<IconPencil size={14} />}
              disabled={menuItems.length !== 1}
              onClick={() => browser.setRenaming({ path: menuItems[0].path, value: menuItems[0].name })}
            >
              重命名
            </Menu.Item>
            <Menu.Item
              color="red"
              leftSection={<IconTrash size={14} />}
              disabled={!menuItems.length}
              onClick={() => browser.remove(menuItems)}
            >
              删除
            </Menu.Item>
            <Menu.Divider />
          </>
        )}
        <Menu.Item
          leftSection={<IconFolderPlus size={14} />}
          onClick={() => {
            browser.navigate(menuTarget);
            browser.setCreating('');
          }}
        >
          在 {where} 里新建文件夹
        </Menu.Item>
        <Menu.Item
          leftSection={<IconClipboard size={14} />}
          disabled={!browser.clipboard}
          onClick={() => void browser.pasteInto(menuTarget)}
        >
          粘贴
        </Menu.Item>
        <Menu.Item leftSection={<IconUpload size={14} />} onClick={() => void browser.upload()}>
          上传本地文件到 {where}
        </Menu.Item>
        <Menu.Divider />
        <Menu.Item leftSection={<IconCopy size={14} />} onClick={browser.selectAll}>
          全选
        </Menu.Item>
        <Menu.Item leftSection={<IconRefresh size={14} />} onClick={() => void browser.listing.refetch()}>
          刷新
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
