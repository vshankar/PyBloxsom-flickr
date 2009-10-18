"""
    Flickr plugin for PyBloxsom (http://pyblosxom.sourceforge.net)
    This plugin calls flickr apis to get a users photo from flickr.com
    The returned markup from this plugin is in HTML table format i.e.
    <tr>
        <td></td>
        <td></td>
    <tr>
        <td></td>
        <td></td>

    The number of rows and colums for the table can be configured
    in config.py
	
    Option for caching the markup is also provided. Data is cached
    in memcache, so you would need memcached to be installed + me-
    cached client for python, get it from here :-

    http://www.tummy.com/Community/software/python-memcached/

    OR use any package manager (apt-get, yum etc...) to install
    python-memcached.

    config.py configuration
    -----------------------
    # flickr authentication key, secret and auth
    py["flickrKey"] = "XXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    py["flickrSecret"] = "XXXXXXXXXXXXXXXXX"
    py["flickrAuth"] = "XXXXXXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXX"

    # number of rows and colums of the table to be returned
    (defaults to 2x3)
    py["flickrNrRows"] = 3
    py["flickrNrCols"] = 3

    # cache enable, timeout === 1 Hr
    py["cacheEnabled"] = 1
    py["cacheTimeout"] = 1 * 60 *60

"""

__author__ = "Venky Shankar - venkyshankar at yahoo dot com"
__description__ = "Show random Flickr photos from your account on your blog."

"""
    Constants
"""
TABLE_START_ROW = r'<tr>'
TABLE_START_COL = r'<td>'
TABLE_END_COL = r'</td>'
STR_FMT = "%d"

DEFAULT_NR_ROWS = 2
DEFAULT_NR_COLS = 3

FLICKR_API_FORMAT = r'http://api.flickr.com/services/rest/?%s'
FLICKR_SIGNATURE = r'%sapi_key%sauth_token%s%s'

FLICKR_URL_THUMB_FORMAT = r'http://farm%s.static.flickr.com/%s/%s_%s_t.jpg'
FLICKR_URL_LINK_FORMAT = r'http://www.flickr.com/photos/%s/%s/'

CACHE_KEY = r'/pyFlickr/%d/%d'

import hashlib
import random

class PyBlGenFlickrHTML:
    def __init__(self, request):
        self._request = request
        self._flickrXML = None
        self._flickrHTML = None
        self._flickrNrRows = 0
        self._flickrNrCols = 0
        self._flickrKey = None
        self._flickrSecret = None
        self._flickrAuth = None
        self._cacheTimeout = 0
        self.getFlickrMarkup()

    def __str__(self):
        return self._flickrHTML

    def genFlickrFlattenStr(self, fa):
        flattenArgs = ''
        sortedKeys = fa.keys()
        sortedKeys.sort()
        for k in sortedKeys:
            flattenArgs += k + fa[k]
        return flattenArgs

    def genFlickrRawStr(self, s):
        return (FLICKR_SIGNATURE % (self._flickrSecret,self._flickrKey,self._flickrAuth,s))

    def getFlickrXMlData(self, pg):
        """
            Call flickr photo search API with the required
            parameters and store the response in _flickrXML
        """
        flickrArgs = {}
        flickrArgs["method"] = "flickr.photos.search"
        flickrArgs["page"] = STR_FMT % pg
        flickrArgs["per_page"] = STR_FMT % (self._flickrNrRows*self._flickrNrCols)
        flickrArgs["privacy_filter"] = STR_FMT % 1
        flickrArgs["user_id"] = "me"

        rawFlickrAuthStr = self.genFlickrRawStr(self.genFlickrFlattenStr(flickrArgs))

        m = hashlib.md5()
        m.update(rawFlickrAuthStr)

        flickrArgs["api_key"] = self._flickrKey
        flickrArgs["auth_token"] = self._flickrAuth
        flickrArgs["api_sig"] = m.hexdigest()

        import urllib
        param = urllib.urlencode(flickrArgs)
        self._flickrXML = urllib.urlopen(FLICKR_API_FORMAT % param).read()

    def start_element(self, name, attrs):
        if name == 'photos':
            self._flickrHTML = r'<tr>'
            return
        if name == 'photo':
            self._flickrHTML += r'<td><a href="' + FLICKR_URL_LINK_FORMAT % (attrs["owner"],attrs["id"]) + r'">'
            self._flickrHTML += r'<img src="' + FLICKR_URL_THUMB_FORMAT % (attrs["farm"],attrs["server"],attrs["id"],attrs["secret"]) + r'"></a>'

    def end_element(self, name):
        if name == 'photo':
            self._flickrHTML += r'</td>'
            self._flickrNrCols -= 1

            if self._flickrNrCols == 0:
                self._flickrNrRows -= 1
                if self._flickrNrRows > 0:
                    self._flickrHTML += r'<tr>'
                    self._flickrNrCols = self._request.getConfiguration().get("flickrNrRows", DEFAULT_NR_ROWS)

    def parseFlickrXMlToHTML(self):
        """
            Parse the XML stored in _flickrXML
            and generate the table markup.
        """
        import xml.parsers.expat

        p = xml.parsers.expat.ParserCreate()

        p.StartElementHandler = self.start_element
        p.EndElementHandler = self.end_element
        p.Parse(self._flickrXML)

    def checkCache(self, mc):
        total = self._flickrNrRows*self._flickrNrCols

        currPhotoPages = mc.get_multi(['flickrPhotoCount', 'flickrNrPhotos'])

        if not (('flickrPhotoCount' in currPhotoPages) and ('flickrNrPhotos' in currPhotoPages)):
            return 0

        nrPages = int(currPhotoPages['flickrPhotoCount'])
        nrPhotos = int(currPhotoPages['flickrNrPhotos'])

        nrPagesExpected = nrPhotos / total
        if nrPhotos % total != 0:
            nrPagesExpected += 1

        if (nrPages == nrPagesExpected):
            rPage = random.randint(1, nrPages)
            self._flickrHTML = mc.get(CACHE_KEY % (rPage, total))
            return rPage
        return 0

    def cacheData(self, mc, k, v):
        """
            Cache data with the given key
            for timwout in _cacheTimeout.
        """
        mc.set(k, v, self._cacheTimeout)

    def cacheMultiData(self, mc, dict):
        """
            Same as above but for multiple
            key/values.
        """
        mc.set_multi(dict, self._cacheTimeout)

    def getFlickrMarkup(self):
        config = self._request.getConfiguration()
        self._flickrNrRows = config.get("flickrNrRows", DEFAULT_NR_ROWS)
        self._flickrNrCols = config.get("flickrNrCols", DEFAULT_NR_COLS)
        total = self._flickrNrRows*self._flickrNrCols

        self._flickrKey = config.get("flickrKey", None)
        self._flickrSecret = config.get("flickrSecret", None)
        self._flickrAuth = config.get("flickrAuth", None)

        mc = None
        memCacheServers = ()
        useCaching = config.get("cacheEnabled", 0)
        if useCaching > 0:
            import memcache
            memCacheServers = config.get("cacheServers", '127.0.0.1:11211')
            self._cacheTimeout = config.get("cacheTimeout", 0)
            mc = memcache.Client(memCacheServers, debug=0)

            rPage = self.checkCache(mc)
            if rPage > 0:
                if self._flickrHTML == None:
                    self.getFlickrXMlData(rPage)
                    self.parseFlickrXMlToHTML()
                    self.cacheData(mc, CACHE_KEY % (rPage, total), self._flickrHTML)
                return

        self.getFlickrXMlData(1)

        import re
        m = re.search('pages="(\d+)".*total="(\d+)"', self._flickrXML)
        currPhotoPages = m.group(1)
        currTotalPhotos = m.group(2)

        if int(currPhotoPages) == 0:
            return

        rPage = random.randint(1, int(currPhotoPages))
        if rPage != 1:
            self.getFlickrXMlData(rPage)

        self.parseFlickrXMlToHTML()
        if useCaching > 0:
            self.cacheMultiData(mc, {CACHE_KEY % (rPage, total): self._flickrHTML, 'flickrPhotoCount': currPhotoPages, 'flickrNrPhotos': currTotalPhotos})

        return

def cb_prepare(args):
    request = args["request"]
    data = request.getData()
    data["flickrHTML"] = PyBlGenFlickrHTML(request)



