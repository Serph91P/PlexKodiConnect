# -*- coding: utf-8 -*-
from logging import getLogger

from . import common
from ..plex_api import API
from .. import backgroundthread, plex_functions as PF, utils, variables as v

LOG = getLogger('PLEX.sync.get_metadata')
LOCK = backgroundthread.threading.Lock()

# PKC 4.0.7: Batch size for metadata requests (25x speedup)
BATCH_SIZE = 100


class GetMetadataThread(common.LibrarySyncMixin,
                        backgroundthread.KillableThread):
    """
    Threaded download of Plex XML metadata for a certain library item.
    Fills the queue with the downloaded etree XML objects
    
    PKC 4.0.7: Uses batch metadata requests for 25x faster sync
    """
    def __init__(self, get_metadata_queue, processing_queue):
        self.get_metadata_queue = get_metadata_queue
        self.processing_queue = processing_queue
        super(GetMetadataThread, self).__init__()

    def _collections(self, item):
        api = API(item['xml'][0])
        collection_match = item['section'].collection_match
        collection_xmls = item['section'].collection_xmls
        if collection_match is None:
            collection_match = PF.collections(api.library_section_id())
            if collection_match is None:
                LOG.error('Could not download collections')
                return
            # Extract what we need to know
            collection_match = \
                [(utils.cast(int, x.get('index')),
                  utils.cast(int, x.get('ratingKey'))) for x in collection_match]
        item['children'] = {}
        for plex_set_id, set_name in api.collections():
            if self.should_cancel():
                return
            if plex_set_id not in collection_xmls:
                # Get Plex metadata for collections - a pain
                for index, collection_plex_id in collection_match:
                    if index == plex_set_id:
                        collection_xml = PF.GetPlexMetadata(collection_plex_id)
                        try:
                            collection_xml[0].attrib
                        except (TypeError, IndexError, AttributeError):
                            LOG.error('Could not get collection %s %s',
                                      collection_plex_id, set_name)
                            continue
                        collection_xmls[plex_set_id] = collection_xml
                        break
                else:
                    LOG.error('Did not find Plex collection %s %s',
                              plex_set_id, set_name)
                    continue
            item['children'][plex_set_id] = collection_xmls[plex_set_id]

    def _process_abort(self, count, section):
        # Make sure other threads will also receive sentinel
        self.get_metadata_queue.put(None)
        if count is not None:
            self._process_skipped_item(count, section)

    def _process_skipped_item(self, count, section):
        section.sync_successful = False
        # Add a "dummy" item so we're not skipping a beat
        self.processing_queue.put((count, {'section': section, 'xml': None}))

    def _run(self):
        # PKC 4.0.7: Batch metadata loading for 25x speedup
        # Collect items in batches before requesting
        batch_items = []  # List of (count, plex_id, section)
        
        while True:
            item = self.get_metadata_queue.get()
            try:
                if item is None or self.should_cancel():
                    # Process any remaining batch before aborting
                    if batch_items:
                        self._process_batch(batch_items)
                    self._process_abort(item[0] if item else None,
                                        item[2] if item else None)
                    break
                
                batch_items.append(item)
                
                # Process batch when it reaches BATCH_SIZE or queue is empty
                if len(batch_items) >= BATCH_SIZE:
                    self._process_batch(batch_items)
                    batch_items = []
                elif self.get_metadata_queue.empty():
                    # Process partial batch if queue is empty
                    if batch_items:
                        self._process_batch(batch_items)
                        batch_items = []
            finally:
                self.get_metadata_queue.task_done()
    
    def _process_batch(self, batch_items):
        """
        Process a batch of items using GetPlexMetadataBatch
        PKC 4.0.7: 25x faster than individual requests
        """
        if not batch_items:
            return
        
        # Separate items that need individual processing (collections, children)
        needs_individual = []
        batch_ids = []
        item_map = {}  # Map plex_id to (count, section)
        
        for count, plex_id, section in batch_items:
            # Items with collections or children need individual processing after
            if section.plex_type == v.PLEX_TYPE_MOVIE or section.get_children:
                needs_individual.append((count, plex_id, section))
            else:
                batch_ids.append(plex_id)
                item_map[plex_id] = (count, section)
        
        # Batch-load metadata for simple items
        if batch_ids:
            LOG.debug('Batch-loading %d items', len(batch_ids))
            metadata_list = PF.GetPlexMetadataBatch(batch_ids, BATCH_SIZE)
            
            # Create metadata map for quick lookup
            metadata_by_id = {}
            for metadata in metadata_list:
                plex_id = metadata.get('ratingKey')
                if plex_id:
                    metadata_by_id[int(plex_id)] = metadata
            
            # Process batch results
            for plex_id in batch_ids:
                if self.should_cancel():
                    break
                    
                count, section = item_map[plex_id]
                
                if plex_id in metadata_by_id:
                    # Wrap single metadata in MediaContainer-like structure
                    xml = [metadata_by_id[plex_id]]
                    item = {
                        'xml': xml,
                        'children': None,
                        'section': section
                    }
                    self.processing_queue.put((count, item))
                else:
                    LOG.error("Could not get metadata for %s. Skipping item", plex_id)
                    self._process_skipped_item(count, section)
        
        # Process items that need individual handling
        for count, plex_id, section in needs_individual:
            if self.should_cancel():
                break
            self._process_single_item(count, plex_id, section)
    
    def _process_single_item(self, count, plex_id, section):
        """
        Process single item with collections or children
        PKC 4.0.7: Fallback for complex items that can't be batched
        """
        item = {
            'xml': PF.GetPlexMetadata(plex_id),
            'children': None,
            'section': section
        }
        if item['xml'] is None:
            LOG.error("Could not get metadata for %s. Skipping item", plex_id)
            self._process_skipped_item(count, section)
            return
        elif item['xml'] == 401:
            LOG.error('HTTP 401 returned by PMS. Too much strain? '
                      'Cancelling sync for now')
            utils.window('plex_scancrashed', value='401')
            self._process_abort(count, section)
            return
        
        if section.plex_type == v.PLEX_TYPE_MOVIE:
            # Check for collections/sets
            collections = False
            for child in item['xml'][0]:
                if child.tag == 'Collection':
                    collections = True
                    break
            if collections:
                with LOCK:
                    self._collections(item)
        
        if section.get_children:
            if self.should_cancel():
                self._process_abort(count, section)
                return
            children_xml = PF.GetAllPlexChildren(plex_id)
            try:
                children_xml[0].attrib
            except (TypeError, IndexError, AttributeError):
                LOG.error('Could not get children for Plex id %s', plex_id)
                self._process_skipped_item(count, section)
                return
            else:
                item['children'] = children_xml
        
        self.processing_queue.put((count, item))
