#pylint:disable=E1101
import googleapiclient.discovery, time, sys, warnings, random, datetime, json, os
from google.oauth2 import service_account
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from paramiko import SSHClient, AutoAddPolicy, SSHException, ssh_exception

warnings.filterwarnings(action='ignore',module='.*paramiko.*')
warnings.filterwarnings(action='ignore',message='Your application has authenticated using end user credentials')

def get_database_credentials():
    dbinfo = {}
    if os.environ.get("DBADDRESS") and os.environ.get("DBUSER") and os.environ.get("DBPASSWORD") and os.environ.get("DBPORT") and os.environ.get("DBNAME") == None:
        dbinfo['dbaddress'] = os.environ.get("DBADDRESS")
        dbinfo['dbuser'] = os.environ.get("DBUSER")
        dbinfo['dbpassword'] = os.environ.get("DBPASSWORD")
        dbinfo['dbport'] = os.environ.get("DBPORT")
        dbinfo['dbname'] = os.environ.get("DBNAME")
    else:
        try:
            with open('config.json') as config:
                conf = json.load(config)
                dbinfo['dbaddress'] = conf['dbaddress']
                dbinfo['dbuser'] = conf['dbuser']
                dbinfo['dbpassword'] = conf['dbpassword']
                dbinfo['dbport'] = conf['dbport']
                dbinfo['dbname'] = conf['dbname']
        except Exception as ex:
            print(ex)

    return dbinfo

dbinfo = get_database_credentials()

engine = create_engine('mysql://{}:{}@{}:{}/{}?charset=utf8'.format(dbinfo['dbuser'], dbinfo['dbpassword'], dbinfo['dbaddress'], dbinfo['dbport'], dbinfo['dbname']))
Session = sessionmaker(bind=engine)
session = Session()

Base = declarative_base()

class TemplateUpdate(Base):
    __tablename__ = 'templatedata'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8', 'mysql_collate': 'utf8_general_ci'}

    id = Column(Integer, primary_key=True)
    friendly_name = Column(String(250))
    project = Column(String(150))
    region = Column(String(100))
    zone = Column(String(100))
    instance_name = Column(String(250))
    image_prefix = Column(String(100))
    source_template_name = Column(String(250))
    template_prefix = Column(String(100))
    instance_group_name = Column(String(250))
    family = Column(String(100))
    ssh_command = Column(String(250))

    def __repr__(self):
        return "<TemplateData(id='{}', friendly_name='{}', project='{}', region='{}'," \
               " zone='{}', instance_name='{}', image_prefix='{}, template_prefix='{}'," \
               " family='{}', instance_group_name='{}', source_template_name='{}', ssh_command='{}' >" \
               .format(self.id, self.friendly_name, self.project, self.region, self.zone, self.instance_name,\
                    self.image_prefix, self.template_prefix, self.family, self.instance_group_name, self.source_template_name, self.ssh_command)


Base.metadata.create_all(engine)

if len(sys.argv) != 4:  
    sys.exit()
else:
    FRIENDLY_NAME = sys.argv[1]
    USERNAME = sys.argv[2]
    KEYFILE = sys.argv[3]

result = session.query(TemplateUpdate).filter(TemplateUpdate.friendly_name == FRIENDLY_NAME).first()

if result != None:
    SUFFIX = "-" + str(datetime.date.today()) + "-" + (str(random.randint(1, 200)))
    PROJECT = result.project
    REGION = result.region
    ZONE = result.zone
    INSTANCE_NAME = result.instance_name
    IMAGE_NAME = result.image_prefix + SUFFIX
    TEMPLATE_NAME = result.template_prefix + SUFFIX
    INSTANCE_GROUP_NAME = result.instance_group_name
    FAMILY = result.family
    SOURCE_TEMPLATE_NAME = result.source_template_name
    SSH_COMMAND = result.ssh_command
else:
    print('No matching friendly_name found')
    sys.exit(1)

compute = googleapiclient.discovery.build('compute', 'v1')
computeBeta = googleapiclient.discovery.build('compute', 'beta')

def main():

    compute.instances().start(project=PROJECT, zone=ZONE, instance=INSTANCE_NAME).execute()

    instanceStatus = compute.instances().get(project=PROJECT, zone=ZONE, instance=INSTANCE_NAME).execute()

    while instanceStatus["status"] != "RUNNING":
        print('Waiting for instance startup')
        time.sleep(60)
        instanceStatus = compute.instances().get(project=PROJECT, zone=ZONE, instance=INSTANCE_NAME).execute()

    instance = compute.instances().get(project=PROJECT, zone=ZONE, instance=INSTANCE_NAME).execute()

    if "accessConfigs" in instance["networkInterfaces"][0]:
        publicIP = instance["networkInterfaces"][0]["accessConfigs"][0]["natIP"]
    else:
        publicIP = instance["networkInterfaces"][0]["networkIP"]

    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    try:
        client.connect(publicIP, username=USERNAME, key_filename=KEYFILE)
        stdin, stdout, stderr = client.exec_command(SSH_COMMAND)
        print('##### Normal Output #####\n {}'.format(stdout.readlines()))
        print('##### ERROR ##### \n {}'.format(stderr.readlines()))
    except SSHException as ex:
        print("Connection error: {}".format(ex))
        sys.exit()
    except Exception as ex:
        print("Random error: {}".format(ex))
        sys.exit()
    finally:
        client.close()

    while True:
        letter = ''
        if sys.version_info[0] >= 3:
            letter = input('Continue (y/n)? ').lower()
        else:
            letter = raw_input('Continue (y/n)? ').lower().strip('\r')
        if letter == 'y':
            break
        else:
            sys.exit()

    stop = compute.instances().stop(project=PROJECT, zone=ZONE, instance=INSTANCE_NAME).execute()
    wait_for_operation(compute, project=PROJECT, zone=ZONE, operation=stop["name"])

    IMAGESPEC = {'name': IMAGE_NAME,
                 'sourceDisk': 'projects/{0}/zones/{1}/disks/{2}'.format(PROJECT, ZONE, INSTANCE_NAME),
                 'family': FAMILY, 'forceCreate': 'true'}

    compute.images().insert(project=PROJECT, body=IMAGESPEC).execute()
    image = compute.images().get(project=PROJECT, image=IMAGE_NAME).execute()

    while image['status'] != 'READY':
        print('Waiting for image creation')
        time.sleep(10)
        image = compute.images().get(project=PROJECT, image=IMAGE_NAME).execute()

    instanceTemplateResponse = compute.instanceTemplates().get(project=PROJECT, instanceTemplate=SOURCE_TEMPLATE_NAME).execute()
    instanceTemplateResponse['name'] = TEMPLATE_NAME
    instanceTemplateResponse['properties']['disks'][0]['deviceName'] = IMAGE_NAME
    instanceTemplateResponse['properties']['disks'][0]['initializeParams']['sourceImage'] = 'projects/{}/global/images/{}'.format(PROJECT, IMAGE_NAME)

    compute.instanceTemplates().insert(project=PROJECT, body=instanceTemplateResponse).execute()
    time.sleep(10)

    instanceGroupManager = compute.regionInstanceGroupManagers().get(
        project=PROJECT, region=REGION, instanceGroupManager=INSTANCE_GROUP_NAME).execute()

    updatePolicy = {
        'updatePolicy': {
            'type': 'PROACTIVE',
            'minimalAction': 'REPLACE',
            'maxSurge': {'fixed': '3'},
            'maxUnavailable': {'fixed': '0'},
            'minReadySec': '0',
        },
        'fingerprint': instanceGroupManager['fingerprint'],
        'name': instanceGroupManager['name'],
        'baseInstanceName': instanceGroupManager['name'],
        'targetSize': instanceGroupManager['targetSize'],
        'instanceTemplate': 'projects/{}/global/instanceTemplates/{}'.format(PROJECT, TEMPLATE_NAME),
        'namedPorts': instanceGroupManager['namedPorts'],
        'autoHealingPolicies': instanceGroupManager["autoHealingPolicies"]
    }

    computeBeta.regionInstanceGroupManagers().update(
        project=PROJECT, region=REGION, instanceGroupManager=INSTANCE_GROUP_NAME, body=updatePolicy).execute()
    print('All done!')

# [START wait_for_operation]
def wait_for_operation(compute, project, zone, operation):
    print('Waiting for operation to finish...')
    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation).execute()

        if result['status'] == 'DONE':
            print("done.")
            if 'error' in result:
                raise Exception(result['error'])
            return result

        time.sleep(1)
# [END wait_for_operation]


main()
