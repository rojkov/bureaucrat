Quick start
===========

Bureaucrat is a workflow engine using AMQP for message passing between the
engine, participants and the rest of the world. The participants can be
either `Celery`_ tasks or `taskqueue`_ workers.

Run `bureaucrat --help` to see the supported options. Most probably you'll
see something like::

    Usage: bureaucrat [options]

    Options:
      -h, --help            show this help message and exit
      -f, --foreground      don't daemonize
      -c CONFIG, --config=CONFIG
                            path to config file
      -p PIDFILE, --pid-file=PIDFILE

If you don't provide any config file the engine will asume more or less
sensible defaults. Check `config file example`_ to see what are the possible
configuration parameters.

A new process can be launched by publishing its definition to bureaucrat's AMQP
exchange with the routing key `bureaucrat`. A better alternative is to use an
instance of class `bureaucrat.launcher.Launcher` to do that. The launcher's
method `Launcher.launch()` accepts two parameters:

 1. process definition and
 2. fields.

The second parameter sets the root context of a new process instance.

At the momemnt the engine supports only one format for process definitions
which resembles the format used in the BPML specification. Check this `process
definition example`_ to see how it looks like.

Any process definition must have one root element `<process>`. The element may
contain `<context>` definition which sets the process's context. This context
definition is an alternative to the `fields` parameter of
`Launcher.launcher()`. The other `<process>`'s children are activities which are
exeuted sequentially.

Supported activities
--------------------

`sequence`
    a complex activity used to organize sequential activities.

`action`
    a simple activity that performs a task in the configured task queue.
    Execution pauses until the task is completed. The task name must be
    specified in the attribute `participant`. In case the configured task queue
    is Celery the task name must be a fully qualified function name e.g.
    `webhook_launcher.tasks.handle_webhook`. Every task is supposed to
    report its `status` in the response message. If `status` is `done`
    then the task is considered complete and the engine furthers execution.
    In case `status` is set to `critical` then a fault is thrown in the current
    context. All other statuses will be just reported in logs.

`switch`
    a complex activity implementing conditional execution.

`while`
    a complex activity implementing cyclic execution with a precondition.

`all`
    a complex activity implementing parallel execution of its child activities.
    The activity doesn't complete until all its children complete.

`call`
    a simple activity launching a new subprocess. The attribute `process` of
    the activity refers the definition of the subprocess. At the moment
    only reference to `context` is supported. E.g.
    `<call process="$proc">` launches a subprocess defined in the current
    `context['proc']`.

    The parent process pauses until the subprocess completes.

`delay`
    a simple activity pausing execution for the duration specified in the
    parameter `duration` in seconds.

`await`
    a simple activity pausing execution until a global event with the name
    specified in the parameter `event` gets triggered, e.g.::

       <await event="fake_event_name">
           <condition>context["precondition"] is True</condition>
       </await>

    The events get triggered by publishing a specially crafted message to
    the default AMQP exchange with the routing key `bureaucrat_events`.
    The event message is a JSON object with an event name specified
    in the attribute `event`, e.g.::

        {
            "event": "fake_event_name",
            "other_data": "some data"
        }

    Additionally the activity may be guarded with one or more `<condition>`
    child elements. Their syntax is the same as in the `switch` activity.

`fault`
    a simple activity throwing a fault into the current context. Optionally
    the fault's code and message can be defined. Consider the following
    example::

        <process>
            <context><property name="prop1" type="int">0</property></context>
            <action participant="p1" />
            <switch>
                <case>
                    <condition>context["prop1"] &gt; 0</context>
                    <action participant="p3" />
                </case>
                <case>
                    <condition>True</context>
                    <fault code="CustomError" message="prop1 hasn't been incremented in the previous action" />
                </case>
            </switch>
            <action participant="p3" />
        </process>

    If the participant `p1` doesn't increment the value of the property `prop1`
    then the process will be aborted and the participant `p3` won't be
    executed.

    If a fault is thrown in a nested complex activity and there is no a
    corresponding fault handler defined in the activity's context then the fault
    will be propagated upward until the root expression is reached or a fault
    handler defined in a outter context handles the fault.

`assign`
    a simple activity setting or updating a property's value in the current
    context, e.g. in the following example the value of `prop1` will be set
    to 8 when the `action` activity is reached::

        <process>
            <context>
                <property name="prop1" type="int">0</property>
                <property name="prop2" type="int">3</property>
            </context>
            <assign property="prop1">context["prop2"] + 5</assign>
            <action participant="p1" />
        </process>

Additional expressions
--------------------

It is possible handle thrown faults with fault handlers defined in the
context where the faults are thrown to::

    <process>
        <sequence>
            <context>
                <faults>
                    <case code="SomeError, AnotherError">
                        <action participant="some_error_cure" />
                    </case>
                    <default>
                        <action participant="general_cure" />
                    </default>
                </faults>
            </context>
            <action participant="faulty_particpant" />
        </sequence>
    </process>

.. important:: If you are going to use Celery make sure that Celery is
   configured to ignore task results and to resend workitems back to the
   default AMQP exchange with the routing key `bureaucrat_msgs`::

        import pika
        import json
        from celery.signals import task_success

        @task_success.connect
        def handle_task_success(sender=None, **kwargs):
            """Report task results back to workflow engine."""

            parameters = pika.ConnectionParameters(host="localhost")
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.basic_publish(exchange='',
                                  routing_key='bureaucrat_msgs',
                                  body=json.dumps(kwargs["result"]),
                                  properties=pika.BasicProperties(
                                      delivery_mode=2,
                                      content_type='application/x-bureaucrat-message'
                                  ))
            connection.close()

.. _config file example: https://github.com/rojkov/bureaucrat/blob/master/examples/config.ini
.. _process definition example: https://github.com/rojkov/bureaucrat/blob/master/examples/processes/example1.xml
.. _Celery: http://www.celeryproject.org/
.. _taskqueue: https://github.com/rojkov/taskqueue
