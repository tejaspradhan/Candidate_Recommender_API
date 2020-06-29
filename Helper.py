import re
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
import io
import os
import PyPDF2
import requests
import json
import pymongo
from pymongo import MongoClient
import pickle 
import gensim
from gensim.test.utils import get_tmpfile

class Helper:
    def __init__(self):
        self.stop_words = stopwords.words('english')
        

    def cleanTextAndTokenize(self, text):
        
        #KEEP ALPHABATES, SPACE
        #LOWER CASE
        lemmatizer = WordNetLemmatizer()
        text = re.sub('[^A-Za-z ]+', ' ', text).lower()
        tokens = word_tokenize(text)
        cleanToken = []
        for token in tokens:
            if(token not in self.stop_words):
                cleanToken.append(token)
        cleanToken = [lemmatizer.lemmatize(x) for x in cleanToken]
        return cleanToken

    
    def createDictionary(self, ex):
        
        url = "https://hrlanesprodstorage1.blob.core.windows.net/public/master.json"
        master = requests.get(url)
        data = master.json()
        obj_ind = data['IndustryData']
        broad = data['BroadAreaData']
        country = data['countryData']
        exp = [i['value'] for i in data['ExperienceData']]
        ind = {}
        for i in obj_ind:
            ind[i['value']] = i['label']
        farea = {}
        subf = {}
        for f in broad:
            farea[f['value']] = f['label']
            if 'sub' in f:
                subf[f['value']] = f['sub']
        con = {}
        for c in country:
            con[c['value']] = c['label']

        #dictionary: {(func_area, exp): [(cand_id1, match_text), (cand_id2, match_text)..], ...}
        hard_filter = []
        for i in farea:
            for j in exp:
                hard_filter.append((i,j))

        d = {}
        for filter in hard_filter:
            d[filter] = []

        for item in ex:
            text = ''
            if 'ProfileName' in item['ProfileSummaryInfo']:
                text+=item['ProfileSummaryInfo']['ProfileName'] 
            if 'Industry' in item['ProfileSummaryInfo']:
                text+=ind[item['ProfileSummaryInfo']['Industry']] 
            if 'FunctionalAreas' in item['ProfileSummaryInfo'] and item['ProfileSummaryInfo']['FunctionalAreas']!= None:
                for i in range(len(item['ProfileSummaryInfo']['FunctionalAreas'])):
                    if 'FunctionValue' in item['ProfileSummaryInfo']['FunctionalAreas'][i]:
                        f = item['ProfileSummaryInfo']['FunctionalAreas'][i]['FunctionValue']
                        text+=farea[f]
                        text+=' '
                        for j in range(len(item['ProfileSummaryInfo']['FunctionalAreas'][i]['SubFunValue'])):
                            sf = item['ProfileSummaryInfo']['FunctionalAreas'][i]['SubFunValue'][j]
                            for s in data[subf[f]]:
                                if s['value']==sf:
                                    text+=s['label']
                                    break           
            if 'FileName' in item['ProfileSummaryInfo'] and item['ProfileSummaryInfo']['FileName'] != None:
                fname = item['ProfileSummaryInfo']['FileName']
                userid = item['_id']
                fpath = 'https://hrlanesprodstorage1.blob.core.windows.net/container'+str(userid)+'/resume/'+fname+'?sv=2019-10-10&ss=b&srt=co&sp=r&se=2099-06-08T13:36:56Z&st=2020-06-08T05:36:56Z&spr=https&sig=Nx2rJ734l%2BBiTpJGpReuNizfg%2BgGa1jlyFs8cXjE76I%3D'    
                try:
                    r = requests.get(fpath)
                    f = io.BytesIO(r.content)
                    reader = PyPDF2.PdfFileReader(f)
                    pages =  reader.getNumPages()
                    pdftext = ''
                    for i in range(pages): 
                        pdftext += reader.getPage(i).extractText()
                        text+=pdftext
                except:
                    text+=' '
            if 'EducationDetails' in item['ProfileSummaryInfo'] and item['ProfileSummaryInfo']['EducationDetails']!= None:
                for i in range(len(item['ProfileSummaryInfo']['EducationDetails'])):
                    text+=item['ProfileSummaryInfo']['EducationDetails'][i]['AreaOfStudy']
                    text+=' '
                    text+=item['ProfileSummaryInfo']['EducationDetails'][i]['Degree']
                    text+=' '
                    text+=item['ProfileSummaryInfo']['EducationDetails'][i]['Description']
                    text+=' '
            if 'EmploymentDetails' in item['ProfileSummaryInfo'] and item['ProfileSummaryInfo']['EmploymentDetails']!= None:
                for i in range(len(item['ProfileSummaryInfo']['EmploymentDetails'])):
                    text+=item['ProfileSummaryInfo']['EmploymentDetails'][i]['Company']
                    text+=' '
                    text+=item['ProfileSummaryInfo']['EmploymentDetails'][i]['Location']
                    text+=' '
                    text+=con[item['ProfileSummaryInfo']['EmploymentDetails'][i]['Country']] 
                    text+=' '
                    text+=item['ProfileSummaryInfo']['EmploymentDetails'][i]['Title'] 
                    text+=' '
                    text+=item['ProfileSummaryInfo']['EmploymentDetails'][i]['Role']
                    text+=' '
            if 'ProjectDetails' in item['ProfileSummaryInfo']and item['ProfileSummaryInfo']['ProjectDetails']!= None:
                for i in range(len(item['ProfileSummaryInfo']['ProjectDetails'])):
                    text+=item['ProfileSummaryInfo']['ProjectDetails'][i]['Title']
                    text+=' '
                    text+=item['ProfileSummaryInfo']['ProjectDetails'][i]['RoleAndResponsibility']
                    text+=' '
                    text+=item['ProfileSummaryInfo']['ProjectDetails'][i]['DescriptionAndDeliverables']
                    text+=' '
            if 'OtherDetailsInfo' in item:
                text+=item['OtherDetailsInfo']['Overview']
                text+=' '
            if 'LocationInfo' in item:
                text+=item['LocationInfo']['City']
            if 'ExperienceLevel' in item['ProfileSummaryInfo']:
                e = item['ProfileSummaryInfo']['ExperienceLevel']
                for i in range(len(item['ProfileSummaryInfo']['FunctionalAreas'])):
                    fid = item['ProfileSummaryInfo']['FunctionalAreas'][i]['Funct_id']
                    if (fid, e) not in d:
                        d[(fid,e)] = []
                    d[(fid, e)].append((item['_id'], text))
        return d

    def create_tfidf(self, name, documents, included):
        try:
            '''dictionary = gensim.corpora.Dictionary(documents)
            with open(str(name)+"_resume.dict", "wb+") as fp:
                pickle.dump(dictionary, fp)
            corpus = [dictionary.doc2bow(text) for text in documents]
            model = gensim.models.TfidfModel(corpus)
            model.save(str(name)+"_tfidf.model")
            index_tmpfile = get_tmpfile('similarity_object')
            similarity_object = gensim.similarities.Similarity(index_tmpfile,model[corpus],num_features=len(dictionary))
            similarity_object.save(str(name)+'_similarity_index.0')
            with open(str(name)+"_doc_included.list", "wb+") as fp:
                pickle.dump(included, fp)
            '''
        except:
            pass
    def recommend(self, ex, fn, cleanToken):
        '''
            Function takes in experience, functional area, tokenized job description and recommends candidate IDs
        '''
        name = (int(fn), int(ex))
        try:
            path = os.getcwd()+"\\"
            dictionary = gensim.corpora.Dictionary.load(path+str(name)+"_resume.dict")
            model = gensim.models.TfidfModel.load(path+str(name)+"_tfidf.model")
            similarity_obj = gensim.similarities.Similarity.load(path+str(name)+"_similarity_index.0")
            doc_included = list(pickle.load(open(path+str(name)+"_doc_included.list", "rb+")))
            cleaned_bow = dictionary.doc2bow(cleanToken) #bag of words of job description
            cleaned_tfidf = model[cleaned_bow] #tfidf of JD

            sim_scores = similarity_obj[cleaned_tfidf]
            scores = []
            for i in range(len(doc_included)):
                scores.append((sim_scores[i],doc_included[i]))
            scores.sort(reverse = True)
            sscores = []
            for (i,j) in scores:
                sscores.append((j,i))
            return sscores

        except:
            return []    
    def extract_text_from_url(self, url):
        try:
            r = requests.get(url)
            f = io.BytesIO(r.content)
            reader = PyPDF2.PdfFileReader(f)
            pages =  reader.getNumPages()
            pdftext = ''
            for i in range(pages): 
                pdftext += reader.getPage(i).extractText()
            return pdftext
        except:
            pdftext+=' '
            return pdftext    
