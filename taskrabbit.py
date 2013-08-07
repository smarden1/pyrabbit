from pyoauth2 import AccessToken, Client as oAuthClient
import simplejson, collections

class TaskRabbitError(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)

Endpoint = collections.namedtuple("Endpoint", ["url", "method"])

class TaskRabbit(object):
    """
        main entry point into the api
    """

    URL             = "https://taskrabbitdev.com"
    AUTHORIZE_URL   = "https://taskrabbitdev.com/api/authorize"
    TOKEN_URL       = "https://taskrabbitdev.com/api/oauth/token"
    APP_KEY         = ""
    APP_SECRET      = ""
    REDIRECT_URL    = ""

    ENDPOINTS = {
        "city"          : Endpoint("/api/v1/cities/{0}", "get"),
        "account"       : Endpoint("/api/v1/account", "get")
        "user"          : Endpoint("/api/v1/users/{0}", "get"),
        "task"          : Endpoint("/api/v1/tasks/{0}", "get"),
        "task_close"    : Endpoint("/api/v1/tasks/{0}/close", "post"),
        "task_comment"  : Endpoint("/api/v1/tasks/{0}/comments", "post"),
        "offer"         : Endpoint("/api/v1/tasks/{0}/offers", "get"),
        "offer_accept"  : Endpoint("/api/v1/tasks/{0}/offers/{1}/accept", "post"),
        "offer_counter" : Endpoint("/api/v1/tasks/{0}/offers/{1}/counter", "post"),
        "offer_decline" : Endpoint("/api/v1/tasks/{0}/offers/{1}/decline", "post"),
    }

    Client = oAuthClient(TaskRabbit.APP_KEY, TaskRabbit.APP_SECRET,
                site = URL,
                authorize_url = AUTHORIZE_URL,
                token_url = TOKEN_URL,
                header_format = 'OAuth %s')

    @staticmethod
    def createAuthorizeUrl():
        return TaskRabbit.Client.auth_code.authorize_url(redirect_uri=TaskRabbit.REDIRECT_URL)

    @staticmethod
    def setSecrets(key, secret, REDIRECT_URL=""):
        TaskRabbit.APP_KEY      = key
        TaskRabbit.APP_SECRET   = secret

    # TODO: make a static to load this from a external file or dictionary
    def __init__(self, user_token):
        self.user_token = user_token

        self.access_token = AccessToken(
            client=TaskRabbit.Client,
            token=user_token,
            header_format='OAuth %s')

        self.headers = {
            'X-Client-Application': TaskRabbit.APP_SECRET
        }

        # memoized city dict
        self.city_dict = {}

    def __request(self, endpoint, method="get", **opts):
        """
            main entrypoint to the api, should only be called by request
        """
        if method not in ["get", "post", "delete"]:
            raise TaskRabbitError("method must be either get or post or delete, received : " + str(method))

        func        = getattr(self.access_token, method)
        response    = func(endpoint, headers=self.headers, **opts)

        if response.status not in [301, 201, 200]:
            raise TaskRabbitError("Erroneous Response From TaskRabbit : " + str(response.status))

        return simplejson.loads(response.body)

    def request(self, name, id = [""], override_method = False, **opts):
        """
            makes a request to the named api endpoint
        """
        if name not in TaskRabbit.ENDPOINTS:
            raise TaskRabbitError("unknown endpoint name : " + str(name))

        end_point = TaskRabbit.ENDPOINTS[name]
        id = [id] if type(id) != type([]) else id

        return self.__request(end_point.url.format(*id), override_method or end_point.method, **opts)

    def findCityId(self, city_name):
        """
            given a city name, returns the city id
        """
        if len(self.city_dict) == 0:
            self.city_dict = dict((i.name.lower(), i.id) for i in self.cities())

        return self.city_dict[city_name.lower()]

    def cities(self):
        """
            lists all cities (returns an array of City)
        """
        return map(lambda a: City(self, **a), self.request("city")["items"])

    # todo - the null case
    def findCity(self, city_id):
        """
            returns a City for the given city_id
        """
        return City(self, **self.request("city", [city_id]))

    # todo - the null case
    def findUser(self, user_id):
        """
            returns a User for the given user_id
        """
        return User(self, **self.request("user", [user_id]))

    # todo - the null case
    def findTask(self, task_id):
        """
            returns a Task for the given task_id
        """
        return Task(self, **self.request("task", [task_id]))

    def findTasks(self):
        """
            find all tasks for the api user
        """
        return map(lambda a: Task(self, **a), self.request("task")["items"])

    def createTask(self, name, named_price_in_dollars, city, **kwargs):
        """
            creates a task for a user
        """
        kwargs.update({
            "name"          : name,
            "named_price"   : named_price_in_dollars,
            "city"          : self.findCityId(city)
        })

        return Task(self, **self.request("task", "", "post", data={"task" : kwargs}))

    def findAccount(self):
        """
            returns this User
        """
        return User(self, **self.request("account"))

class Base(object):
    """
        generic class to represent return data
        this should be extended
    """
    def __init__(self, request, **kwargs):
        self.request = request

        for k, v in kwargs.iteritems():
            if k == "city":
                self.city = City(self.request, **v)
            elif k == "user":
                self.user = User(self.request, **v)
            elif k == "task":
                self.task = Task(self.request, **v)
            else:
                setattr(self, k, v)

    def __str__(self):
        return repr(self)


class City(Base):
    """
        Users live in cities and tasks happen within cities,
        Cities should have an id and a name
    """
    def __repr__(self):
        return "%s : %s" % (self.id, self.name)

class User(Base):
    """
        users live in cities, can make tasks, and negotiate them (accept, decline, counter, etc)
    """
    def __repr__(self):
        return "%s : %s" % (self.id, self.display_name)

class Offer(object):
    """
        offers occur between users in regards to a specific task,
        i.e. John accepts an offer from Bob to paint his house
    """
    def __init__(self, request, task_id, **kwargs):
        super().__init__()
        self.task_id = task_id

    def __repr__(self):
        return "task_id : %s, offer_id : %s, offer_state : %s, price : %s" % (self.task_id, self.id, self.state, self.charge_price)

    def accept(self):
        """
            accept this offer
        """
        return Offer(self.request, **self.request.request("offer_accept", [self.task_id, self.id]))

    def decline(self):
        """
            decline this offer
        """
        return Offer(self.request, **self.request.request("offer_decline", [self.task_id, self.id]))

    def counter(self, charge_price, comments):
        """
            counter this offer with a new price and a comment
        """
        data = {"charge_price" : charge_price, "comments" : comments}
        return Offer(self.request, **self.request.request("offer_counter", [self.task_id, self.id], data=data))

class Task(Base):
    """
        tasks are the unit of exchange
        they are created by a user, negotiated by another, and then completed
    """
    def __repr__(self):
        return "%s : %s" % (self.id, self.name)

    # better close procedures
    # can close reimburse and do other things here
    # TODO - make sure this is correct
    def close(self):
        """
            close this task
        """
        return self.request.request("task_close", self.id)["state"] == "closed"

    def delete(self):
        """
            delete this task
        """
        return self.request.request("task", self.id, "delete")

    # verify that this is working
    def comment(self, comment):
        """
            comment on this task
        """
        data = {"comment" : {"content" : comment}}
        return self.request.request("task_comment", self.id, data=data)

