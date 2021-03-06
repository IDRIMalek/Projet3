import uvicorn
import json
import secrets
from enum import Enum
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import JSONResponse
import pandas as pd
from typing import Optional
from pydantic import BaseModel
from neo4j import GraphDatabase



app = FastAPI(title='Compatibilities cv->project with neo4j')

security = HTTPBasic()
#base de donnée utilisateurs
users_db = {
    "alice": "wonderland",
    "bob": "builder",
    "clementine": "mandarine"
}

driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'neo4j'))

# chargement des données initiales 
# requête pour charger les noeuds
queryinit1="""
LOAD CSV WITH HEADERS FROM "file:///stack_network_nodes.csv" AS row 
MERGE (:language {name: row.name, 
                    group: row.group, 
                    nodesize: row.nodesize });
"""
# requête pour charger les liens
queryinit2="""
LOAD CSV WITH HEADERS FROM "file:///stack_network_links.csv" AS row 
MATCH (a:language) WHERE a.name = row.source 
MATCH (b:language) WHERE b.name = row.target AND a.name <> b.name
MERGE (a)-[l:link {value: toFloat(row.value)} ]->(b);

"""
# Chargement des données
with driver.session() as session:
    result=session.run(queryinit1).data()
    print("neo4j datas nodes loaded..........")
    result=session.run(queryinit2).data()
    print("neo4j datas links loaded..........")


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = True if credentials.username in users_db else False
    print("username", credentials.username)
    print("password", credentials.password)
    print("correct_username", correct_username)
    correct_password = False
    if (correct_username):
        correct_password = secrets.compare_digest(credentials.password, users_db[credentials.username])
        print("correct_password", correct_password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get('/')
def get_index():
    return {'data': 'hello world'}

@app.get('/status')
def get_status():
    return {
        'status': 'ready'
    }

@app.get('/listtechno',tags=["Informations"])
def listtechno(username: str = Depends(get_current_username)):
    '''
    This query allow you to see all node languages. 
    '''
    query='Match (n:language) Return n.name;'
    with driver.session() as session:
        result=session.run(query).data()
    return {'results': result}

@app.get('/listgroup',tags=["Informations"])
def listgroup(username: str = Depends(get_current_username)):
    '''
    This query allow you to see all kind of labels(groups). 
    '''
    query='Match (n) Return distinct(labels(n));'
    with driver.session() as session:
        result=session.run(query).data()
    return {'results': result}

@app.get('/listlink',tags=["Informations"])
def listlink(username: str = Depends(get_current_username)):
    '''
    This query allow you to see all kind of relationships. 
    '''
    query='MATCH (n)-[l]-(m)RETURN distinct(TYPE(l));'
    with driver.session() as session:
        result=session.run(query).data()
    return {'results': result}

@app.post('/addcandidate',tags=["Interaction"])
def addcandidate(name, skill ,  username: str = Depends(get_current_username)):
    '''
    This query allow you to add skill(languages)a candidate. 
    '''
    name=name.lower()
    skill=skill.lower()
    query="MERGE (n:candidate{name:'"+name+"',group:'candidate', nodesize:'1'}) MERGE (m:language {name:'"+skill+"'}) CREATE (n)-[:link]->(m)  Return n.name, ID(n);"
    with driver.session() as session:
        result=session.run(query).data()
    return {'node added': result}


@app.post('/addprojet',tags=["Interaction"])
def addprojet(name, neededskill,  username: str = Depends(get_current_username)):
    '''
    This query allow you to add a project. 
    '''
    name=name.lower()
    neededskill=neededskill.lower()
    query="MERGE (n:project{name:'"+name+"',group:'project', nodesize:'1'}) MERGE (m:language {name:'"+neededskill+"'}) CREATE (n)-[:link]->(m) Return n.name, ID(n);"
    with driver.session() as session:
        result=session.run(query).data()
    return {'node added': result}


@app.get('/matchprojet',tags=["Informations"])
def matchprojet(username: str = Depends(get_current_username)):
    '''
    This query allow you to see nodes matching projects for all candidates, up to seconde degrees 
    '''
    query="""
    MATCH (c:candidate)-[rc:link]->(sc:language)-[rc2:link]->(sc2:language) , (p:project)-[rp:link]->(sp:language)-[rp2:link]->(sp2:language) 
    WITH collect(distinct sc.name) as l , collect(distinct sc2.name) as l2, collect(distinct sp.name) as lp , collect(distinct sp2.name) as lp2, c, p
    WITH l, l2, lp, lp2, size(lp) as skillsneed, size(lp2) as skill2sneed, c, p
    WITH [n IN l WHERE n IN lp ] as matchskills1, [n IN l2 WHERE n IN lp2 ]as matchskills2, skillsneed, skill2sneed, c, p
    RETURN c.name as candidate, p.name as project, round(size(matchskills1))/skillsneed as first_degree_compatibility,round(size(matchskills2)/skill2sneed) as second_degree_compatibility, matchskills1, matchskills2
    """
    
    with driver.session() as session:
        result=session.run(query).data()
    return {'results': result}

@app.post('/delete',tags=["Interaction"])
def delete(name,username: str = Depends(get_current_username)):

    '''
    This query allow you to one particular node. 
    '''
    name=name.lower()
    query="Match (n) WHERE n.name= '"+ name +"' DETACH DELETE n;"
    with driver.session() as session:
        result=session.run(query).data()
    return {'results': result}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
