#!/usr/bin/python2.5

#Copyright(c)2009 Internet Archive. Software license GPL version 3.

"""
This script is a proxy that formats solr queries as OPDS
"""

import sys
sys.path.append("/petabox/www/bookserver")

import web
import time
import string
import urllib
import simplejson as json
import xml.etree.ElementTree as ET

numRows = 50

# You can customize pubInfo:
pubInfo = {
    'name'     : 'Internet Archive',
    'uri'      : 'http://www.archive.org',
    'opdsroot' : 'http://bookserver.archive.org'
}

urls = (
    '/(.*)/',               'redirect',
    '/alpha.xml',           'alphaList',
    '/alpha/(.)(?:/(.*))?', 'alpha',
    '/downloads.xml',       'downloads',
    '/',                    'index',
    '/(.*)',                'indexRedirect',        
    )

application = web.application(urls, globals()).wsgifunc()


# createTextElement()
#______________________________________________________________________________
def createTextElement(parent, name, value):
    element = ET.SubElement(parent, name)
    element.text = value
    return element

# createOpdsRoot()
#______________________________________________________________________________
def createOpdsRoot(title, nss, relurl, datestr):
    ### TODO: add updated element and uuid element
    opds = ET.Element("feed")
    opds.attrib['xmlns'] = 'http://www.w3.org/2005/Atom'
        
    createTextElement(opds, 'title',    title)
    urn = 'urn:x-internet-archive:bookserver:' + nss
    createTextElement(opds, 'id',       urn)

    createTextElement(opds, 'updated',  datestr)
    
    absurl = pubInfo['opdsroot'] + relurl
    element = ET.SubElement(opds, 'link')
    element.attrib['rel'] = 'self'
    element.attrib['type'] = 'application/atom+xml'
    element.attrib['href'] = absurl;
    
    author = ET.SubElement(opds, 'author')
    createTextElement(author, 'name',  pubInfo['name'])
    createTextElement(author, 'uri',   pubInfo['uri'])
        
    return opds
    

# createOpdsEntry()
#______________________________________________________________________________
def createOpdsEntry(opds, title, nss, url, datestr, content):
    entry = ET.SubElement(opds, 'entry')
    createTextElement(entry, 'title', title)

    urn = 'urn:x-internet-archive:bookserver:' + nss
    createTextElement(entry, 'id',       urn)

    createTextElement(entry, 'updated',  datestr)

    element = ET.SubElement(entry, 'link')
    element.attrib['type'] = 'application/atom+xml'
    element.attrib['href'] = url;
    
    if content:
        createTextElement(entry, 'content',  content)

# createOpdsEntryBook()
#______________________________________________________________________________
def createOpdsEntryBook(opds, item):
    
    if not 'title' in item:
        return

    id = item['identifier']

    entry = ET.SubElement(opds, 'entry')
    
    createTextElement(entry, 'title', item['title'])

    urn = 'urn:x-internet-archive:item:' + id
    createTextElement(entry, 'id',       urn)

    if 'creator' in item:
        for author in item['creator']:
            element = ET.SubElement(entry, 'author')
            createTextElement(element, 'name', author)

    if 'oai_updatedate' in item:
        createTextElement(entry, 'updated', item['oai_updatedate'][-1]) #this is sorted, get latest date

    url = 'http://www.archive.org/download/%s/%s.pdf' %(id, id)
    element = ET.SubElement(entry, 'link')
    element.attrib['type'] = 'application/pdf'
    element.attrib['href'] = url;


    ### create content element
    ### FireFox won't show the content element if it contains nested html elements
    contentText=''

    if 'creator' in item:
        if 1 == len(item['creator']):
            authorStr = '<b>Author: </b>'
        else:
            authorStr = '<b>Authors: </b>'
        
        authorStr += ', '.join(item['creator'])
        contentText += authorStr + '<br/>'

    #TODO: refactor
    if 'subject' in item:
        contentText += '<b>Subject </b>' + ', '.join(item['subject']) + '<br/>'

    if 'publisher' in item:
        contentText += '<b>Publisher: </b>' + ', '.join(item['publisher']) + '<br/>'
        
    if 'date' in item:
        contentText += '<b>Year published: </b>' + item['date'][0:4] + '<br/>'

    if 'contributor' in item:
        contentText += '<b>Book contributor: </b>' + ', '.join(item['contributor']) + '<br/>'

    if 'language' in item:
        contentText += '<b>Language: </b>' + ', '.join(item['language']) + '<br/>'

    if 'month' in item:
        contentText += str(item['month']) + ' downloads in the last month' + '<br/>'

    element = createTextElement(entry, 'content',  contentText)
    element.attrib['type'] = 'html'


# getDateString()
#______________________________________________________________________________
def getDateString():
    #IA is continuously scanning books. Since this OPDS file is constructed
    #from search engine results, let's change the updated date every midnight
    t       = time.gmtime()
    datestr = time.strftime('%Y-%m-%dT%H:%M:%SZ', 
                (t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, 0))
    return datestr

# /
#______________________________________________________________________________
class index:
    def GET(self):
        opds = createOpdsRoot('Internet Archive OPDS', 'opds', '/', getDateString())

        createOpdsEntry(opds, 'All Titles', 'opds:titles:all', 
                        '/alpha.xml', getDateString(),
                        'Alphabetical list of all titles.')

        createOpdsEntry(opds, 'Most Downloaded Books', 'opds:downloads', 
                        '/downloads.xml', getDateString(),
                        'The most downloaded books from the Internet Archive in the last month.')
        
        web.header('Content-Type', 'application/xml')

        return ET.tostring(opds)


# /alpha/a/0
#______________________________________________________________________________
class alpha:
    def makePrevNextLinks(self, opds, letter, start, numFound):
        if 0 != start:
            #from the atom spec:
            title = 'Previous results for books starting with '+letter.upper()
            url = '/alpha/%s/%d' % (letter, start-1)

            element = ET.SubElement(opds, 'link')
            element.attrib['rel']  = 'prev'
            element.attrib['type'] = 'application/atom+xml'
            element.attrib['href'] = url
            element.attrib['title'] = title


        if (start+1)*numRows < numFound:
            #from the atom spec:
            title = 'Next results for books starting with '+letter.upper()
            url = '/alpha/%s/%d' % (letter, start+1)

            element = ET.SubElement(opds, 'link')
            element.attrib['rel']  = 'next'
            element.attrib['type'] = 'application/atom+xml'
            element.attrib['href'] = url
            element.attrib['title'] = title


    ### Add some links to ease navigation in firefox's feed reader
    def makePrevNextLinksDebug(self, opds, letter, start, numFound):
        if 0 != start:
            title = 'Previous results for books starting with '+letter.upper()
            url = '/alpha/%s/%d' % (letter, start-1)

            #this test entry is for easier navigation in firefox #TODO: remove this
            createOpdsEntry(opds, title, 'opds:titles:%s:%d'%(letter, start-1), 
                                url, getDateString(), None)

    
        if (start+1)*numRows < numFound:
            #from the atom spec:
            title = 'Next results for books starting with '+letter.upper()
            url = '/alpha/%s/%d' % (letter, start+1)

            #this test entry is for easier navigation in firefox #TODO: remove this
            createOpdsEntry(opds, title, 'opds:titles:%s:%d'%(letter, start+1), 
                                url, getDateString(), None)
    
            
        createOpdsEntry(opds, 'Alphabetical Title Index', 'opds:titles:all', 
                            '/alpha.xml', getDateString(), None)


    # GET()
    #___________________________________________________________________________
    def GET(self, letter, start):
        if not start:
            start = 0
        else:
            start = int(start)
        
        #TODO: add Image PDFs to this query
        solrUrl = 'http://se.us.archive.org:8983/solr/select?q=firstTitle%3A'+letter+'*+AND+mediatype%3Atexts+AND+format%3A(LuraTech+PDF)&fl=identifier,title,creator,oai_updatedate,date,contributor,publisher,subject,language&sort=titleSorter+asc&rows='+str(numRows)+'&start='+str(start*numRows)+'&wt=json'
        f = urllib.urlopen(solrUrl)        
        contents = f.read()
        f.close()
        obj = json.loads(contents)
        
        numFound = int(obj['response']['numFound'])
        
        title = 'Internet Archive - %d to %d of %d books starting with "%s"' % (start*numRows, min((start+1)*numRows, numFound), numFound, letter.upper())
        opds = createOpdsRoot(title, 'opds:titles:'+letter, 
                        '/alpha/%s/%d'%(letter, start), getDateString())

        self.makePrevNextLinks(opds, letter, start, numFound)
        
        for item in obj['response']['docs']:
            description = None
            
            if 'description' in item:
                description = item['description']

            createOpdsEntryBook(opds, item)

        self.makePrevNextLinksDebug(opds, letter, start, numFound)
        
        web.header('Content-Type', 'application/xml')
        return ET.tostring(opds)
                
        
# /alpha.xml
#______________________________________________________________________________
class alphaList:
    def GET(self):
        #IA is continuously scanning books. Since this OPDS file is constructed
        #from search engine results, let's change the updated date every midnight
        #TODO: create a version of /alpha.xml with the correct updated dates,
        #and cache it for an hour to ease load on solr
        datestr = getDateString()
    
        opds = createOpdsRoot('Internet Archive - All Titles', 'opds:titles:all', 
                                '/alpha.xml', datestr)
        for letter in string.ascii_uppercase:
            lower = letter.lower()
            createOpdsEntry(opds, 'Titles: ' + letter, 'opds:titles:'+lower, 
                                '/alpha/'+lower+'/0', datestr, 
                                'Titles starting with ' + letter)
            
        web.header('Content-Type', 'application/xml')
        return ET.tostring(opds)

# /downloads.xml
#______________________________________________________________________________
class downloads:
    def GET(self):
        #TODO: add Image PDFs to this query
        solrUrl = 'http://se.us.archive.org:8983/solr/select?q=mediatype%3Atexts+AND+format%3A(LuraTech+PDF)&fl=identifier,title,creator,oai_updatedate,date,contributor,publisher,subject,language,month&sort=month+desc&rows='+str(numRows)+'&wt=json'
        f = urllib.urlopen(solrUrl)        
        contents = f.read()
        f.close()
        obj = json.loads(contents)

        opds = createOpdsRoot('Internet Archive - Most Downloaded Books in the last Month', 
                              'opds:downloads', '/downloads.xml', getDateString())
                              
        for item in obj['response']['docs']:
            createOpdsEntryBook(opds, item)

        web.header('Content-Type', 'application/xml')
        return ET.tostring(opds)

# redirect to remove trailing slash
#______________________________________________________________________________        
class redirect:
    def GET(self, path):
        web.seeother('/' + path)

# redirect to index
#______________________________________________________________________________        
class indexRedirect:
    def GET(self, path):
        web.seeother('/')


if __name__ == "__main__":
    #run in standalone mode
    app = web.application(urls, globals())
    app.run()