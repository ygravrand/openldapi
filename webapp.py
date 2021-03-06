#! /usr/bin/env python

from flask import Flask, jsonify, request, abort, make_response
import ldap
import ldap.modlist as modlist
import json
import getConfig
from ldapConn import ldapConn

app = Flask(__name__)


def getNextgidNumber():
    ''' return the next available gidNumber
    for a new group to be created'''
    result = api_getAllGroups('gidNumber')
    gidlist = []
    dictresult = json.loads(result.get_data())
    for gidtuple in dictresult.items():
        if len(gidtuple[1]) != 0:
            print gidtuple[1]
            gidlist.append(int(gidtuple[1]['gidNumber']))
    return max(gidlist) + 1


@app.route('/api/v1/user/<username>/', methods=['GET'])
def api_getUser(username):
    '''
    Endpoint returning every attributes for asked username
    '''
    search_filter = "{}={}".format(getConfig.user_attr, username)
    result = ldapConn(getConfig.user_ou, search_filter)
    if not result:
        return make_response(jsonify({username: "N'existe pas"}), 400)
    for dn, entry in result:
        for key, value in entry.items():
            entry[key] = ",".join(value)
    dictresult = {}
    dictresult[result[0][0]] = result[0][1]
    return jsonify(dictresult)


@app.route('/api/v1/users/all/', methods=['GET'])
def api_getAllUsers():
    '''
    Endpoint returning all the users
    Eeturns paginated results with optional parameters
    limit: number of result to return (default to max)
    offset: index of the first result (default to 1)
    ie /api/V1/users/all/?offset=1&limit=50
    TODO : Add first, next, previous, last page in header
    TODO : Partial Content Header
    '''
    search_filter = "(objectclass=*)"
    result = ldapConn(getConfig.user_ou, search_filter, [getConfig.user_attr])
    sorted_result = sorted(result, key=lambda x: x[1])
    dictresult = {}
#    for elem in result[1:]:
    for elem in sorted_result[1:]:
        entry = {}
        dn = elem[0]
        for key, value in elem[1].items():
            entry[key] = value[0]
        dictresult[dn] = entry
    total_range = len(dictresult.keys())
    range_start = request.args.get('offset', 1)
    range_start = int(range_start) - 1
    range_limit = request.args.get('limit', total_range)
    range_end = range_start + int(range_limit)
    # Case Sensitive sorted results
    req_range = {k: dictresult[k] for k in
                 sorted(dictresult.keys())[range_start:range_end]}
#                  this sorted code tries to sort case insensitive
#                  Not working well
#                 sorted(dictresult.keys(),
#                        key=lambda y: y.lower())[range_start:range_end]}
    return jsonify(req_range)


@app.route('/api/v1/group/<groupname>/', methods=['GET'])
def api_getGroup(groupname):
    '''
    Endpoint returning every attributes for asked group
    '''
    search_filter = "{}={}".format(getConfig.group_attr, groupname)
    result = ldapConn(getConfig.group_ou, search_filter)
    if not result:
        return make_response(jsonify({groupname: "N'existe pas"}), 400)
    for dn, entry in result:
        for key, value in entry.items():
            entry[key] = ",".join(value)
    dictresult = {}
    dictresult[result[0][0]] = result[0][1]
    return jsonify(dictresult)


@app.route('/api/v1/groups/all/', methods=['GET'])
def api_getAllGroups(attr=getConfig.group_attr):
    '''
    Endpoint returning all the groups
    Pagination included
    '''
    search_filter = "(objectclass=*)"
    if 'attr' in request.args:
        attr = str(request.args.get('attr'))
    result = ldapConn(getConfig.group_ou, search_filter, [attr])
    sorted_result = sorted(result, key=lambda x: x[1])
    dictresult = {}
    for elem in sorted_result:
        print elem
        entry = {}
        if elem[0].startswith("cn"):
            dn = elem[0]
            for key, value in elem[1].items():
                entry[key] = value[0]
            dictresult[dn] = entry
        total_range = len(dictresult.keys())
        range_start = request.args.get('offset', 1)
        range_start = int(range_start) - 1
        range_limit = request.args.get('limit', total_range)
        range_end = range_start + int(range_limit)
    # Case Sensitive sorted results
        req_range = {k: dictresult[k] for k in
                     sorted(dictresult.keys())[range_start:range_end]}
    return jsonify(req_range)


@app.route('/api/v1/members/<groupname>/', methods=['GET'])
def api_getGroupMembers(groupname):
    '''
    Endoint returning list of users in group
    '''
    search_filter = "(objectclass=*)"
    search_ou = "{}={},{}".format(
                           getConfig.group_attr,
                           groupname,
                           getConfig.group_ou)
    result = ldapConn(search_ou, search_filter, [getConfig.member_attr])
    return jsonify(result[0][1])


@app.route('/api/v1/memberof/<username>/', methods=['GET'])
def api_getMemberOf(username):
    '''
    Endpoint returning list of groups for a user
    '''
    search_filter = "(&({}=*)({}={}))".format(
                                       getConfig.group_attr,
                                       getConfig.member_attr,
                                       username)
    result = ldapConn(getConfig.base_dn, search_filter)
    output = []
    for dn, entry in result:
        output.append(entry[getConfig.group_attr][0])
    dictresult = {}
    dictresult["memberof"] = output
    return jsonify(dictresult)


@app.route('/api/v1/add/user/', methods=['POST'])
def api_createUser():
    '''
    Endpoint adding a new user
    Request should provide a json dictionnary
    groups key is not mandatory
    {
      uid: username,
      givenName: givenname,
      sn: surname,
      o: organisation,
      mail: email@mail.com,
      telephoneNumber: 0555555555,
      groups: [group1,group2,group3]
    }
    '''
    if not request.json or \
       'uid' not in request.json or \
       'givenName' not in request.json or \
       'sn' not in request.json or \
       'o' not in request.json or\
       'mail' not in request.json:
        abort(400)
    attrs = {}
    attrs['uid'] = str(request.json['uid'])
    attrs['givenName'] = str(request.json['givenName'])
    attrs['sn'] = str(request.json['sn'])
    attrs['cn'] = "{} {}".format(attrs['givenName'], attrs['sn'])
    attrs['o'] = str(request.json['o'])
    attrs['mail'] = str(request.json['mail'])
    attrs['telephoneNumber'] = str(request.json['telephoneNumber'])
    if 'personalTitle' in request.json:
        attrs['personalTitle'] = str(request.json['personalTitle'])
    attrs['objectClass'] = ['top',
                            'person',
                            'inetOrgPerson',
                            'pilotPerson',
                            'organizationalPerson',
                            'OpenLDAPperson',
                            'SIBObject']
    dn = 'uid={},{}'.format(attrs['uid'], getConfig.user_ou)
    ldif = modlist.addModlist(attrs)
    try:
        connect = ldap.initialize('ldap://{0}:{1}'.format(
                                                    getConfig.ldap_server,
                                                    getConfig.ldap_port))
        connect.bind_s(getConfig.ldapcred, getConfig.ldappass)
        connect.add_s(dn, ldif)
    except ldap.LDAPError as e:
        connect.unbind_s()
        return make_response(jsonify({"Erreur LDAP": e.message['desc']}), 400)
    connect.unbind_s()
    return api_getUser(attrs['uid'])


@app.route('/api/v1/add/group/', methods=['POST'])
def api_createGroup():
    if not request.json or \
       'cn' not in request.json:
        abort(400)
    attrs = {}
    attrs['cn'] = str(request.json['cn'])
#    attrs['displayName'] = attrs['cn']
    if 'description' in request.json:
        attrs['description'] = str(request.json['description'])
    attrs['objectClass'] = ['top', 'posixGroup']
    if 'gidNumber' in request.json:
        attrs['gidNumber'] = str(request.json['gidNumber'])
    else:
        attrs['gidNumber'] = str(getNextgidNumber())
    dn = 'cn={},{}'.format(attrs['cn'], getConfig.group_ou)
    ldif = modlist.addModlist(attrs)
    try:
        connect = ldap.initialize('ldap://{0}:{1}'.format(
                                                   getConfig.ldap_server,
                                                   getConfig.ldap_port))
        connect.bind_s(getConfig.ldapcred, getConfig.ldappass)
        connect.add_s(dn, ldif)
    except ldap.LDAPError as e:
        connect.unbind_s()
        return make_response(jsonify({"Erreur LDAP": e.message['desc']}), 400)
    connect.unbind_s()
    return api_getGroup(attrs['cn'])


@app.route('/api/v1/group_edit/<action>/<group>/<username>/', methods=['PUT'])
def api_updateGroupMember(action, group, username):
    if action not in ['add', 'remove']:
        return make_response(jsonify({"Erreur d'action":
                                      "L'action doit etre 'add' ou 'remove'"}),
                             400)
    groupres = api_getGroup(group)
    if groupres.status_code != 200:
        return make_response(jsonify({"Erreur":
                                      "Parsing group"}),
                             400)
    usernameres = api_getUser(username)
    if usernameres.status_code != 200:
        return make_response(jsonify({"Erreur":
                                     "Parsing username"}),
                             400)
    userlistres = api_getGroupMembers(group)
    userlist = json.loads(userlistres.get_data())[getConfig.member_attr]
    userlist = [x.encode('UTF8') for x in userlist]
    newuserlist = userlist[:]
    newuserlist.append(str(username))
    dn = json.loads(groupres.get_data()).keys()[0]
    ldif = modlist.modifyModlist({getConfig.member_attr: userlist},
                                 {getConfig.member_attr: newuserlist})

    try:
        connect = ldap.initialize('ldap://{0}:{1}'.format(
                                                   getConfig.ldap_server,
                                                   getConfig.ldap_port))
        connect.bind_s(getConfig.ldapcred, getConfig.ldappass)
        connect.modify_s(dn, ldif)
    except ldap.LDAPError as e:
        connect.unbind_s()
        return make_response(jsonify({"Erreur LDAP": e.message['desc']}), 400)
    connect.unbind_s()
    return api_getGroup(group)


if __name__ == '__main__':
    app.run(debug=True)
