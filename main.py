import logging
from pathlib import Path
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import ( 
    KeywordQueryEvent, 
)

from ulauncher.api.shared.item.ExtensionSmallResultItem import ExtensionSmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.OpenAction import OpenAction

try:
    from gi.repository import Gtk, Gio
except:
    Gtk, Gio = None, None

DEFAULT_ICON = "images/icon.svg"
IMAGE_EXTENSIONS = (
    '.png',
    '.jpg', 
    '.jpeg',
    '.svg',
    '.gif',
)

logger = logging.getLogger(__name__)

def get_icon_for_file(file, size=256):
    """
    Get the gtk icon path for a specific file or folder (defined by its path).
    """
    path = Path(file.get_uri())
    
    if path.as_posix().lower().endswith(IMAGE_EXTENSIONS):
        return file.get_uri_display()

    if Gtk is not None:
        try: 
            if path.is_dir():
                icon = Gio.content_type_get_icon("folder")
            else:
                mimetype = Gio.content_type_guess(path.name)[0]
                icon = Gio.content_type_get_icon(mimetype)

            theme = Gtk.IconTheme.get_default()
            actual_icon = theme.choose_icon(icon.get_names(), size, 0)
            if actual_icon:
                return actual_icon.get_filename()
        except Exception:
            logger.exception("Failed to get icon for path: %s", path)


    return DEFAULT_ICON

def search_recent_files(search_term, mime_type=None):

    recent_files = Gtk.RecentManager.get_default().get_items()

    if not recent_files:
        raise FileNotFoundError('No recent files found')
    
    if mime_type is not None:
    # Split the MIME type into type and subtype
        type_part, _, subtype_part = mime_type.partition('/')
        recent_files = [
            file for file in recent_files 
            if file.get_mime_type() and 
                (mime_type == file.get_mime_type() or  # Exact match
                (subtype_part == '*' and file.get_mime_type().startswith(f"{type_part}/")))  # Wildcard match
        ]
    
    if search_term:
        recent_files = [file for file in recent_files if search_term in file.get_uri().lower()]

    return sorted(recent_files, key=lambda x: x.get_visited(), reverse=True)  



class RecentFilesExtension(Extension):

    def __init__(self):
        super(RecentFilesExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

class KeywordQueryEventListener(EventListener):

    def on_event(self, event, extension):
        items = []
        arguments = event.get_argument() or ""
        mime_type = None
        search_term = None

        parts = arguments.split()
        if parts and parts[0] in ('f', 'd', 'i', 'v', 'a'):
            search_type = parts[0]
            if search_type == 'f':
                mime_type = 'text/*'
            elif search_type == 'd':
                mime_type = 'inode/directory'
            elif search_type == 'i':
                mime_type = 'image/*'
            elif search_type == 'v':
                mime_type = 'video/*'
            elif search_type == 'a':
                mime_type = 'audio/*'
            search_term = ' '.join(parts[1:]).lower() if len(parts) > 1 else ''
        else:
            mime_type = None
            search_term = arguments.lower()

        try:
            recent_files = search_recent_files(search_term, mime_type)
        except FileNotFoundError as e:
            logger.error(e)
            items.append(ExtensionSmallResultItem(icon=DEFAULT_ICON, name='No recently-used.xbel found'))
            return RenderResultListAction(items)
        except RuntimeError as e:
            logger.error(e)
            items.append(ExtensionSmallResultItem(icon=DEFAULT_ICON, name='No recently-used.xbel found'))
            return RenderResultListAction(items)

        if not recent_files:
            items.append(ExtensionSmallResultItem(icon=DEFAULT_ICON, name='No recent files found'))
            return RenderResultListAction(items)

        for recent_file in recent_files[:20]:
            file_name = recent_file.get_display_name()
            file_path = recent_file.get_uri_display()
            items.append(ExtensionSmallResultItem(icon=(get_icon_for_file(recent_file)),
                                             name=file_name,
                                             on_enter=OpenAction(file_path)))

        return RenderResultListAction(items)


if __name__ == '__main__':
    RecentFilesExtension().run()
