import plyvel
import argparse
import base64
import binascii
from datetime import datetime
import json
import sys


from qrl.generated import qrl_pb2
from google.protobuf.json_format import MessageToJson, Parse, MessageToDict

class getData:
    

    def getBlockHeight(source):
        db = plyvel.DB(source)
        blockheight = int.from_bytes(db.get(b'blockheight'), byteorder='big', signed=False)
        return blockheight
        
    def getBlockData(i, source ):        
        db = plyvel.DB(source)      
        pbdata = qrl_pb2.Block()
        block_number_mapping = qrl_pb2.BlockNumberMapping()            
            
        hashHeader = Parse(db.get(str(i).encode()), block_number_mapping).headerhash
        pbdata.ParseFromString(bytes(db.get(hashHeader)))
        dictData = MessageToDict(pbdata)


        # need to get help getting the following data from plyvel.DB 
        # BlockDataPoint
        # BlockExtended
        
        # see for more information https://api.theqrl.org/?python#block
        
        # neeed to get extended block data 

        blockData = {}
        blockData["block_number"] = i
        blockData["hash_header"] = hashHeader.hex()
        blockData["timestamp"] = datetime.fromtimestamp(int(dictData["header"]["timestampSeconds"]))
        blockData["reward_block"] = dictData["header"]["rewardBlock"]
        blockData["merkle_root"] = dictData["header"]["merkleRoot"] 

        if "hashHeaderPrev" in dictData["header"]:
            blockData["hash_header_prev"] = base64.b64decode(dictData["header"]["hashHeaderPrev"]).hex()

        if "rewardFee" in dictData["header"]:
            blockData["reward_fee"] = dictData["header"]["rewardFee"] 
        
        if "miningNonce" in dictData["header"]:
            blockData["mining_nonce"] = int(dictData["header"]["miningNonce"]) 

        if "extraNonce" in dictData["header"]:
            blockData["extra_nonce"] = int(dictData["header"]["extraNonce"]) 
                
        if "genesisBalance" in dictData:
            blockData["genesis_balance"] = dictData["genesisBalance"][0]["balance"] 
        
        if "transactions" in dictData:
            blockData["transactions"] = dictData["transactions"]

        return blockData
        
    
    def getTransactionData(t, block_number, timestamp):
        tData = {}
        tData["block_number"], tData["timestamp"] = block_number, timestamp 
        tData["transaction_hash"] = base64.b64decode(t["transactionHash"]).hex()
        
        if "masterAddr" in t:
            tData["master_addr"] = "Q" + base64.b64decode(t["masterAddr"]).hex()

        if "publicKey" in t:
            tData["public_key"] = base64.b64decode(t["publicKey"]).hex()

        if "signature" in t:
            tData["signature"] = base64.b64decode(t["signature"]).hex()                                                    
        
        if "nonce" in t:
            tData["nonce"] = t["nonce"]                    

        if "fee" in t:
            tData["fee"] = t["fee"]               
        
        return tData
        
              
    def getTransactionDataCoinbase(t, block_number, timestamp):    
        tData = getData.getTransactionData(t, block_number, timestamp)        
        tData["addr_to"] = "".join(["Q" , base64.b64decode(t["coinbase"]["addrTo"]).hex()]) 
        tData["amount"] = t["coinbase"]["amount"]        
        return tData


    def getTransactionDataTransfer(t, block_number, timestamp, transfer):  
        tData = getData.getTransactionData(t, block_number, timestamp)
        tData["addr_to"] = "".join(["Q" , base64.b64decode(transfer["addr_to"]).hex()])
        tData["amount"] = transfer["amount"]                                             
        return tData
    
        
    def getTransactionDataToken(t, block_number, timestamp):        
        tData = getData.getTransactionData(t, block_number, timestamp)        
        tData["symbol"] = base64.b64decode(t["token"]["symbol"]).decode("utf-8") 
        tData["name"] = base64.b64decode(t["token"]["name"]).decode("utf-8") 
        tData["owner"] = "".join(["Q" , base64.b64decode(t["token"]["owner"]).hex()]) 
        tData["initial_balances"] = t["token"]["initialBalances"]
        tData["initial_balances"] = list(map(lambda x: json.dumps(x), tData["initial_balances"]))
        if "decimals" in t["token"]:
            tData["decimals"] = t["token"]["decimals"]          
        return tData


    def getTransactionDataMessage(t, block_number, timestamp):    
        tData = getData.getTransactionData(t, block_number, timestamp)
        tData["message_hash"] = t["message"]["messageHash"]                 
        try:
            messageHash = base64.b64decode(t["message"]["messageHash"]).decode("utf-8") 
            tData["message_text"] = messageHash
        except:
            messageHash = base64.b64decode(t["message"]["messageHash"]).hex()
            tData["message_text"] = messageHash
             
        #https://github.com/theQRL/qips/blob/master/qips/QIP002.md
        if messageHash.startswith("afaf"):
            if messageHash.startswith("afafa1"):
                try:
                    docText = binascii.a2b_hex(messageHash[46:]).decode("utf-8") 
                except:
                    docText = binascii.a2b_hex(messageHash[46:]).hex()
                tData["message_text"] = " ".join(["[Doc notarization] SHA1:" , messageHash[6:46] , "TEXT:" , docText])   
            elif messageHash.startswith("afafa2"):
                try:
                    docText = binascii.a2b_hex(messageHash[70:]).decode("utf-8") 
                except:
                    docText = binascii.a2b_hex(messageHash[70:]).hex()
                tData["message_text"] = " ".join(["[Doc notarization] SHA256:" , messageHash[6:70] , "TEXT:" , docText]) 
            elif messageHash.startswith("afafa3"):
                try:
                    docText = binascii.a2b_hex(messageHash[38:]).decode("utf-8") 
                except:
                    docText = binascii.a2b_hex(messageHash[38:]).hex()
                tData["message_text"] = " ".join(["[Doc notarization] MD5:" , messageHash[6:38] , "TEXT:" , docText ])   
                
        #https://github.com/theQRL/message-transaction-encoding      
        elif messageHash.startswith("0f0f"):
            msgHeader = "[Unknown]"
            msgBegin = 8
            text = ""
            
            if messageHash.startswith("0f0f0000") or messageHash.startswith("0f0f0001"):
                msgHeader = "[Reserved] "
                
            elif messageHash.startswith("0f0f0002"): 
                if messageHash.startswith("0f0f0002af"): 
                    msgHeader = "[Keybase-remove] "
                elif messageHash.startswith("0f0f0002aa"): 
                    msgHeader = "[Keybase-add] "
                else:
                    msgHeader = "".join(["[Keybase-" , messageHash[8:10] , "]" ])  
                    
                msgBegin = 12
                try:
                    user = binascii.a2b_hex(messageHash[msgBegin:].split("20")[0]).decode("utf-8")
                    keybaseHex = binascii.a2b_hex(messageHash[msgBegin + len(user)*2 + 2:]).hex()
                    text = "".join(["USER:" , user , " KEYBASE_HEX:" , keybaseHex ]) 
                except:
                    text = ""

            elif messageHash.startswith("0f0f0003"):
                if messageHash.startswith("0f0f0002af"): 
                    msgHeader = "[Github-remove] "
                elif messageHash.startswith("0f0f0002aa"): 
                    msgHeader = "[Github-add] "
                else:
                    msgHeader = "".join(["[Github-" , messageHash[8:10] , "] " ])  
                    
                msgBegin = 18
                text = binascii.a2b_hex(messageHash[msgBegin:]).hex()

            elif messageHash.startswith("0f0f0004"):
                msgHeader = "[Vote] "                           
                                     
            if len(text) == 0:                           
                try:
                    text = binascii.a2b_hex(messageHash[msgBegin:]).decode("utf-8")
                except:
                    try:
                        text = binascii.a2b_hex(messageHash[msgBegin:]).hex()
                    except:
                        text = str(messageHash[msgBegin:])
                
            tData["message_text"] = " ".join([msgHeader , text ])
            return tData
    
    
    def getTransactionDataLatticePk(t, block_number, timestamp):
        tData = getData.getTransactionData(t, block_number, timestamp)
        
        print('&&&&&&&&&&&&&')
        print('latticePk - T')
        for key, value in t.items() :
            print(key)
        print('--------------------')     
        print('--------------------') 
        for key, value in t["latticePk"].items() :
            print(key)
        print('^^^^^^^^^^^^^^^^') 

        tData["kyber_pk"] = t["latticePk"]["kyberPK"]
        tData["dilithium_pk"] = t["latticePk"]["dilithiumPK"]    
        return tData    
    
      
    def getTransactionDataSlave(t, block_number, timestamp, transfer):
        tData = getData.getTransactionData(t, block_number, timestamp)
        tData["slave_pk"] = "".join(["Q" , base64.b64decode(transfer["slave_pk"]).hex()])
        tData["access_type"] = transfer["access_type"] 
        return tData


    def getTransactionDataTransferToken(t, block_number, timestamp, transfer):
        tData = getData.getTransactionData(t, block_number, timestamp)
        tData["token_txhash"] = transfer["token_txhash"]
        tData["addr_to"] = "".join(["Q" , base64.b64decode(transfer["addr_to"]).hex()]) 
        tData["amount"] = transfer["amount"] 
        return tData    
    

    def getTransactionDataOthers(t, block_number, timestamp):
        tData = getData.getTransactionData(t, block_number, timestamp)
        print('------------------------')
        print('not transactionProcessed')
        print('------------------------')
        print(t)
        print('------------------------')
                                                    
        if "multiSigCreate" in t:
            tData['type'] = "multiSigCreate"

        if "multiSigSpend" in t:
            tData['type'] = "multiSigSpend"                       

        if "multiSigVote" in t:
            tData['type'] = "multiSigVote"    
                           
        if len(tData['type']) == 0:
            tData['type'] = "unkown"
        
        for key, value in tData.items() :
            print(key)
        print('--------------------')     
        print('--------------------')
        print('transaction unkown')  
        sys.exit("transaction unkown")
        
        tData['data'] = str(t)
        return tData      
    
        
    def getAddressData(source, b64Addr, timeStamp): 
        try:
            addrData = qrl_pb2.AddressState()    
            addrByte = base64.b64decode(b64Addr)
            address = "Q" + addrByte.hex()
            
            db = plyvel.DB(source)
            addrData.ParseFromString(db.get(addrByte))
            dictData = MessageToDict(addrData)


            if (len(dictData) >= 4):
                print('--------------------') 
                for key, value in dictData.items() :
                    print(key)
                print('--------------------')     
                print('--------------------') 
                print('^^^^^^^^^^^^^^^^')
                sys.exit("length of address > 4  check for more data to write") 
        
            addressData = {}    
            if "balance" in dictData:
                addressData["balance"] = dictData["balance"]
    
            if "nonce" in dictData:
                addressData["nonce"] = dictData["nonce"]       
                
            if "otsBitfield" in dictData:
                addressData["ots_bitfield"] = dictData["otsBitfield"]
        
            if "transactionHashes" in dictData:
                addressData["transaction_hashes"] = dictData["transactionHashes"]
     
            if "tokens" in dictData:
                addressData["tokens"] = dictData["tokens"]
                addressData["tokens"] = list(map(lambda x: json.dumps(x), addressData["tokens"]))

            if "latticePKList" in dictData:
                addressData["latticePK_list"] = dictData["latticePKList"]
                addressData["latticePK_list"] = list(map(lambda x: json.dumps(x), addressData["latticePK_list"]))
   
            if "slavePksAccessType" in dictData:
                addressData["slave_pks_access_type"] = dictData["slavePksAccessType"]
                addressData["slave_pks_access_type"] = list(map(lambda x: json.dumps(x), addressData["slave_pks_access_type"]))

            if "otsCounter" in dictData:
                addressData["ots_counter"] = dictData["otsCounter"]

            addressData["last_seen"] = timeStamp
            addressData["first_seen"] = timeStamp  
            addressData["address"] = address
            
            return addressData


        except Exception as e:                
            print(e)
            raise
