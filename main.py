import logging
import os
import collections
import mimetypes
import fnmatch
from urllib.parse import unquote

from pathlib import Path, PurePath
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import ( 
    KeywordQueryEvent, 
)

from ulauncher.api.shared.item.ExtensionSmallResultItem import ExtensionSmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.OpenAction import OpenAction
import xml.etree.ElementTree as ET

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

def get_icon_for_file(path, size=256):
    """
    Get the gtk icon path for a specific file or folder (defined by its path).
    """
    if path.name.lower().endswith(IMAGE_EXTENSIONS):
        return str(path)

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

def search_recent_files(search_term, file_type=None):
    recent_files = collections.deque()

    possible_locations = [
    "~/.local/share/recently-used.xbel",
    "~/.gnome2/recently-used.xbel",
    "~/.kde/share/apps/RecentDocuments/recently-used.xbel",
    "~/.xfce4/recently-used.xbel"
]

    xbel_file = next((os.path.expanduser(location) for location in possible_locations if os.path.exists(os.path.expanduser(location))), None)

    if xbel_file is None:
        raise FileNotFoundError('No recently-used.xbel file found')

    # Parse the XML file
    
    try:
        tree = ET.parse(xbel_file)
        root = tree.getroot()
    except ET.ParseError as e:
        raise RuntimeError(f"Error parsing XBEL file: {e}")

    # Iterate over the <bookmark> elements
    for bookmark in root.findall('bookmark'):
        # Get the file path
        file_path = Path(unquote(bookmark.attrib.get('href').removeprefix('file://')))
        
        # Check if the file still exists
        if not file_path.exists():
            continue

        # Check if file_type is specified and matches the file type
        if file_type is not None:
            if file_type == 'f' and not file_path.is_file():
                continue
            elif file_type == 'd' and not file_path.is_dir():
                continue
            elif file_type in ['v','i','a']:
                mime_type = mimetypes.guess_type(file_path)[0]
                if not mime_type:
                    continue
                elif file_type == 'i':
                    if not mime_type.startswith('image/'):
                        continue
                elif file_type == 'v':
                    if not mime_type.startswith('video/'):
                        continue
                elif file_type == 'a':
                    if not mime_type.startswith('audio/'):
                        continue
            

        # Check if the file path matches the search term
        if search_term in file_path.name.lower():
            if len(search_term) > 2:
                logger.info('Found recent file: %s', file_path)
            recent_files.append(file_path)


    recent_files = list(reversed(recent_files))

    logger.info('Recent files found: %s', len(recent_files))

    return recent_files



class RecentFilesExtension(Extension):

    def __init__(self):
        super(RecentFilesExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())


class KeywordQueryEventListener(EventListener):

    def _is_path_excluded(self, path, excluded_patterns):
        """Check if path matches any of the excluded patterns."""
        path_str = str(path.absolute())
        for pattern in excluded_patterns:
            pattern = pattern.strip()
            if not pattern:
                continue
            # Convert glob pattern to regex and match against full path
            if fnmatch.fnmatch(path_str, pattern) or \
               fnmatch.fnmatch(path_str, f"{pattern}/*") or \
               any(fnmatch.fnmatch(str(p), pattern) for p in path.parents):
                return True
        return False

    def on_event(self, event, extension):
        excluded_dirs = [p.strip() for p in extension.preferences["excluded_dirs"].split(",") if p.strip()]
        excluded_patterns = [
            os.path.expanduser(pattern) if pattern.startswith("~") else pattern 
            for pattern in excluded_dirs
        ]
        logger.info('Excluded patterns: %s', excluded_patterns)
        items = []
        arguments = event.get_argument() or ""

        parts = arguments.split()
        if parts and parts[0] in ('f', 'd', 'i', 'v', 'a'):
            file_type = parts[0]
            search_term = ' '.join(parts[1:]).lower() if len(parts) > 1 else ''
        else:
            file_type = None
            search_term = arguments.lower()

        logger.info('file_type: %s | search_term: %s', file_type, search_term)

        try:
            recent_files = search_recent_files(search_term, file_type)
        except FileNotFoundError as e:
            logger.error(e)
            items.append(ExtensionSmallResultItem(icon=DEFAULT_ICON, name='No recently-used.xbel found'))
            return RenderResultListAction(items)
        except RuntimeError as e:
            logger.error(e)
            items.append(ExtensionSmallResultItem(icon=DEFAULT_ICON, name='No recently-used.xbel found'))
            return RenderResultListAction(items)

        if not recent_files:
            logger.error('No recent files found')
            items.append(ExtensionSmallResultItem(icon=DEFAULT_ICON, name='No recent files found'))
            return RenderResultListAction(items)

        for recent_file in recent_files[:20]:
            if self._is_path_excluded(recent_file, excluded_patterns):
                logger.info("Excluded file: %s", recent_file)
                continue
                
            file_name = recent_file.name
            items.append(ExtensionSmallResultItem(icon=get_icon_for_file(recent_file),
                                             name=file_name,
                                             on_enter=OpenAction(recent_file)))

        return RenderResultListAction(items)


if __name__ == '__main__':
    RecentFilesExtension().run()
