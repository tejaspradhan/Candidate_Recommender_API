from flask import Flask
from pymongo import MongoClient
from Helper import Helper
import pymongo


app = Flask(__name__)
@app.route("/")

def build_model():
    connection = MongoClient('mongodb+srv://hrlanes-mongodb-reader:hrlanes%401234@hrlanes-production-i5mve.mongodb.net', 27017)
    db = connection['hrlanes-web-db']
    data = db['users']
    ex = data.find({"$and": [{'ProfileSummaryInfo': {"$exists": True}}, {'recommenderProcessed': {"$exists": True}}, {'recommenderProcessed': True }]})
    helper = Helper()
    d = helper.createDictionary(ex)
    resumeList = []
    for key in d:
        if len(d[key])>0:  # check if resumes/details exist 
            doc_included = []
            for x in d[key]:
                resumeList.append(x[1])
                doc_included.append(x[0])
            documents = []
            for f in resumeList:
                documents.append(helper.cleanTextAndTokenize(f))
                helper.create_tfidf(str(key), documents, doc_included)
    return "Models Created!"
if __name__ == "__main__":
    app.run(debug=True)