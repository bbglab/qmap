"""Graphical interface built using urwid.

The console is closed when all jobs are in COMPLETED or FAILED stated
and no user input is captured for 30 minutes.
"""

import logging
import time
from os import path
from weakref import WeakMethod

import urwid

from qmap import executor
from qmap.executor import ExecutorError
from qmap.globals import QMapError
from qmap.job import JobStatus
from qmap.job.status import VALUES as JOB_STATUS_VALUES
from qmap.utils import tail

logger = logging.getLogger('qmap')


PARAMS = None
"""Dictionary with the parameters that are editable"""

PARAM_DEFAULT_VALUE = 'default'
TIMER = None


class Timer:

    def __init__(self, secs):
        """Dummy timer class"""
        self._time = secs
        self._start = time.time()
        self.is_running = False  # Flag to avoid generating new timers each time

    @property
    def is_done(self):
        """Check if time has passed or not"""
        return time.time() - self._start > self._time

    def reset(self):
        """Restart the time"""
        self._start = time.time()


def create_button(label, func, extra=None, style=None):
    button = urwid.Button(label)
    urwid.connect_signal(button, 'click', func, extra)
    style_attrs = ('button normal', 'button select') if style is None else style
    return urwid.AttrMap(button, *style_attrs)


def create_buttons_list(items):
    buttons = []
    for i in items:
        buttons.append(create_button(*i))
    return buttons


PALETTE = [
    ('menu header', 'white', 'black', 'bold'),
    ('button normal', 'light gray', 'dark blue', 'standout'),
    ('button select', 'dark gray', 'light cyan'),
    ('pg normal', 'white', 'black', 'standout'),
    ('pg complete', 'white', 'dark magenta'),
    ('editfc', 'black', 'light cyan', 'bold'),
    ('edittxt', 'black', 'dark cyan'),
    ('error msg', 'light red', 'black'),
    ('warning msg', 'yellow', 'black'),
    ('editbx','black','light gray', 'standout'),
    ('stdout', 'white', 'black'),
    ('stderr', 'dark red', 'white'),
    ('retried job', 'white', 'dark red', 'standout'),
    ('retried job select', 'dark red', 'light cyan'),
    ('folder', 'light green', 'black'),
]


class BaseTimedWidgetWrap(urwid.WidgetWrap):

    def keypress(self, *args, **kwargs):
        TIMER.reset()
        return super().keypress(*args, **kwargs)

    def mouse_event(self, *args, **kwargs):
        TIMER.reset()
        return super().mouse_event(*args, **kwargs)


class TextWidget(BaseTimedWidgetWrap):
    """
    Wrapped class of text widgets with update method
    """

    def __init__(self, message):
        self.widget = urwid.Text(message)

        BaseTimedWidgetWrap.__init__(self, self.widget)

    def update(self):
        pass


class ExampleOfInputWithKey(BaseTimedWidgetWrap):

    def __init__(self, text, value, callback):
        """
        Widget with an input field to input real positive integers

        Args:
            text (str): text for the widget
            value (int): default value
            callback: callback function to be called with the new value once the enter key is pressed

        """
        self.input_widget = urwid.IntEdit(('edittxt', text), value)
        self.widget = urwid.Pile([urwid.AttrMap(self.input_widget, 'editbx', 'editfc')])
        BaseTimedWidgetWrap.__init__(self, self.widget)

        self.__f = callback

    def update(self):
        pass

    def keypress(self, size, key):
        key = super().keypress(size, key)
        if key == 'enter':
            self._f()

    def _f(self):
        self.__f(self.input_widget.value())


class YesNoWidget(BaseTimedWidgetWrap):

    def __init__(self, text, callback):
        """
        Widget to select between YES or NO

        Args:
            text (str): text for the widget
            callback: callback function to be called once the enter key is pressed

        """
        self.widget = urwid.Pile([urwid.Text(text), create_button('Yes', self._f, True), create_button('No', self._f, False)])
        BaseTimedWidgetWrap.__init__(self, self.widget)

        self.__f = callback

    def update(self):
        pass

    def _f(self, _, value):
        self.__f(value)


class IntInputWidget(BaseTimedWidgetWrap):

    def __init__(self, text, value, callback):
        """
        Widget with an input field to input real positive integers

        Args:
            text (str): text for the widget
            value (int): default value
            callback: callback function to be called with the new value once the enter key is pressed

        """
        self.input_widget = urwid.IntEdit(('edittxt', text), value)
        self.widget = urwid.Pile([urwid.AttrMap(self.input_widget, 'editbx', 'editfc'), create_button('Submit', self._f)])
        BaseTimedWidgetWrap.__init__(self, self.widget)

        self.__f = callback

    def update(self):
        pass

    def _f(self, _):
        self.__f(self.input_widget.value())


class JobResubmitWidget(BaseTimedWidgetWrap):

    def __init__(self, job, callback=None):
        """
        Widget for resubmitted a job. Allows to enter new parameters for the run and resubmits the job.
        Considered as static widget (update does nothing).


        Args:
            job:
            callback: optional. Called instead of job resubmit if present

        """
        self.job = job

        self.callback = callback

        self.form = {}
        input_boxes = []
        for k, v in PARAMS.items():
            edit_box = urwid.Edit(('edittxt', v + ':  '), str(self.job.params.get(k, PARAM_DEFAULT_VALUE)))
            input_boxes.append(urwid.AttrMap(edit_box, 'editbx', 'editfc'))
            self.form[k] = edit_box

        input_boxes.append(create_button('Resubmit', self.resubmit))

        self.widget = urwid.Padding(urwid.Pile(input_boxes), align='center')

        BaseTimedWidgetWrap.__init__(self, self.widget)

    def update(self):
        pass

    def resubmit(self, _):
        """
        Resubmit the job or call the callback function if provided on construction
        """
        kw = {}
        for k,v in self.form.items():
            if v.edit_text != PARAM_DEFAULT_VALUE:
                kw[k] = v.edit_text
        if self.callback is None:
            try:
                self.job.resubmit(**kw)
            except QMapError as e:
                self.widget.original_widget = urwid.Text(e)
        else:
            self.callback(**kw)


class JobWidget(BaseTimedWidgetWrap):

    def __init__(self, job):
        """
        Widget containing job information and buttons to perform specific job actions.
        The job information is treated as static: only updated if job notifies it.
        However, in a running job, the stdout is shown dynamically.

        Args:
            job:

        """
        self.job = job

        self.info_widgets_list = []  # (sub)widget containing the job information
        self.file_widgets_list = []  # (sub)widget containing the last lines of certain files
        self.metadata_widgets_list = []  # (sub)widget containing the job information from the metadata
        self.update_info()  # read job info

        self.handler = WeakMethod(self.update_info)
        self.job.state_change_handlers.append(self.handler)  # add handler to update information when the job status changes

        self.widget = urwid.Padding(None, align='center')
        self.update()  # add the job info to the widget

        BaseTimedWidgetWrap.__init__(self, self.widget)

    def __del__(self):
        self.job.state_change_handlers.remove(self.handler)  # remove the handler from the job when the object is collected by garbage collector

    @staticmethod
    def _load_file_as_widget(file, attribute_name=None):
        try:
            text_widget = urwid.Text(tail(file))
            if attribute_name is None:
                return text_widget
            else:
                return urwid.AttrMap(text_widget, attribute_name)
        except QMapError:
            # Assume can be because file does not exits
            return None

    def update_info(self, *args, **kwargs):
        """
        Update the job information text.
        Called by the job
        """
        # Create the layout with the information
        self.info_widgets_list = [
            urwid.Text('ID: {}'.format(self.job.id)),
            urwid.Divider('='),
            urwid.Text('Command: {}'.format(self.job.command)),
            urwid.Text('Status: {}'.format(self.job.status))
        ]

        if self.job.status == JobStatus.FAILED:  # If job has failed add error reason (if available)
            if 'Error reason' in self.job.metadata:
                self.info_widgets_list.append(urwid.Text('Possible error reason: {}'.format(self.job.metadata['Error reason'])))

        # Add button with the option available depending on the job status
        if self.job.status in [JobStatus.DONE, JobStatus.FAILED]:
            self.info_widgets_list.append(urwid.Padding(JobResubmitWidget(self.job, callback=self.resubmit), align='center', left=4, right=2))
            self.info_widgets_list.append(urwid.Divider('-'))
        elif self.job.status != JobStatus.UNSUBMITTED:
            self.info_widgets_list.append(create_button('Kill', self.terminate))
            self.info_widgets_list.append(urwid.Divider('-'))

        self.metadata_widgets_list = []
        self.metadata_widgets_list.append(urwid.Text('Retries: {}'.format(self.job.retries)))
        self.metadata_widgets_list.append(urwid.Divider())
        # Add resources requested by the job
        requested_resources = 'Specific requested resources:\n'
        requested_resources += '  '+str(self.job.params).replace('\n', '\n  ')
        self.metadata_widgets_list.append(urwid.Text(requested_resources))

        # If usage information is available, display it
        if 'usage' in self.job.metadata:
            self.metadata_widgets_list.append(urwid.Divider())
            used_resources = 'Used resources:\n'
            used_resources += "\n".join(["  {} = {}".format(k, v) for k, v in self.job.metadata['usage'].items()])
            self.metadata_widgets_list.append(urwid.Text(used_resources))

        self.file_widgets_list = []  # Reset files widget
        # Create widget with the files if the job has failed
        if self.job.status == JobStatus.FAILED:
            # Generate wigets with stdout and stderr if available. Done here because Failed state is "absolute"=
            stdout_widget = self._load_file_as_widget(self.job.f_stdout, 'stdout')
            if stdout_widget is not None:
                self.file_widgets_list.append(stdout_widget)
                self.file_widgets_list.append(urwid.Divider('*'))
            stderr_widget = self._load_file_as_widget(self.job.f_stderr, 'stderr')
            if stderr_widget is not None:
                self.file_widgets_list.append(stderr_widget)
                self.file_widgets_list.append(urwid.Divider('*'))

    def resubmit(self, **kwargs):
        """
        Resubmit the job with new parameters
        """
        try:
            self.job.resubmit(**kwargs)
            self.widget.original_widget = urwid.Text('Trying to resubmit the job...')
        except QMapError as e:
            self.widget.original_widget = urwid.Text(e)

    def terminate(self, _):
        """
        Cancel the job
        """
        try:
            self.job.terminate()
            self.widget.original_widget = urwid.Text('Trying to cancel the job. Wait for update')
        except QMapError as e:
            self.widget.original_widget = urwid.Text(e)

    def update(self):
        """
        Called to update the information displayed
        """
        # even if we change the widget trough the :meth:`resubmit` or :meth:`terminate` methods, go back to the original one
        if self.job.status == JobStatus.RUN:
            # Show stdout of running jobs
            stdout_widget = self._load_file_as_widget(self.job.f_stdout, 'stdout')
            if stdout_widget is not None:
                self.file_widgets_list = [urwid.Pile([stdout_widget, urwid.Divider('*')])]
        self.widget.original_widget = urwid.Pile(self.info_widgets_list + self.file_widgets_list + self.metadata_widgets_list)


class ClusterWidget(BaseTimedWidgetWrap):

    def __init__(self):
        """
        Widget showing information related to the cluster.

        .. note::
           This widget contains an empty edit widget.
           It is useless, however is a hack to enable selecting the widget.
           For some reason, if this widget was not selectable, when replaced
           by the JobWidget, that would not be selectable. [Took a while to find it out]

        """

        self.boxes = [
            urwid.AttrMap(urwid.Text('QMap'), 'menu header'),
            urwid.Divider('=')
        ]

        self.widget = urwid.Padding(None, align='center')
        self.update()

        BaseTimedWidgetWrap.__init__(self, self.widget)

    def update(self):
        new_boxes = []
        try:
            status = executor.get_usage()
        except ExecutorError:
            new_boxes.append(urwid.AttrMap(urwid.Text('Error getting global cluster status'), 'error msg'))
        else:
            # Total usage
            if 'usage' in status:
                usage = status['usage']
                usage_txt = urwid.Text('In use {0:.2f} %'.format(usage))
                if usage > 85:
                    usage_txt = urwid.AttrMap(usage_txt, 'error msg')
                elif usage > 50:
                    usage_txt = urwid.AttrMap(usage_txt, 'warning msg')
                nodes = urwid.Text('Nodes: {}'.format(status.get('nodes', '?')))
                new_boxes.append(urwid.Columns([('weight', 5, usage_txt), ('weight', 5, nodes)]))
            # User usage
            if 'user' in status:
                usage = status['user']
                usage_txt = urwid.Text('You {0:.2f} %'.format(usage))
                if usage > 85:
                    usage_txt = urwid.AttrMap(usage_txt, 'error msg')
                elif usage > 50:
                    usage_txt = urwid.AttrMap(usage_txt, 'warning msg')
                new_boxes.append(usage_txt)

        new_boxes.append(urwid.Edit(''))  # Hack to make selectable working
        info = self.boxes + new_boxes
        self.widget.original_widget = urwid.Pile(info)


class ExecutionParameters(BaseTimedWidgetWrap):

    def __init__(self, execution):
        """
        Widget for changing the execution parameters. Allows to enter new parameters for the run and resubmits the job.
        Considered as static widget (update does nothing).
        """
        self.execution = execution

        self.form = {}
        if len(PARAMS) == 0:
            input_boxes = [] #[urwid.Text('Changing the default parameters not allowed')]
        else:
            input_boxes = [urwid.Text('Change the default parameters for the jobs:')]
            for k, v in PARAMS.items():
                edit_box = urwid.Edit(('edittxt', v + ':  '), str(self.execution.job_params.get(k, PARAM_DEFAULT_VALUE)))
                input_boxes.append(urwid.AttrMap(edit_box, 'editbx', 'editfc'))
                self.form[k] = edit_box

            input_boxes.append(create_button('Change', self.resubmit))

        self.widget = urwid.Padding(urwid.Pile(input_boxes), align='center')

        BaseTimedWidgetWrap.__init__(self, self.widget)

    def update(self):
        pass

    def resubmit(self, _):
        """
        Resubmit the job or call the callback function if provided on construction
        """
        kw = {}
        for k, v in self.form.items():
            if v.edit_text != PARAM_DEFAULT_VALUE:
                kw[k] = v.edit_text
        try:
            self.execution.update_job_params(**kw)
        except QMapError as e:
            self.widget.original_widget = urwid.Text(e)


class ExecutionStatusWidget(BaseTimedWidgetWrap):

    def __init__(self, status):
        """
        Widget containing the execution status

        Args:
            status:

        """

        self.exec_status = status

        # Manager information
        self.progress = urwid.ProgressBar("pg normal", "pg complete",
                                          current=len(self.exec_status.groups[JobStatus.DONE]),
                                          done=self.exec_status.total)
        self.progress_info = urwid.Text(str(self.exec_status))

        self.widget = urwid.Pile([self.progress, self.progress_info])

        BaseTimedWidgetWrap.__init__(self, self.widget)

    def update(self):
        self.progress.set_completion(len(self.exec_status.groups[JobStatus.DONE]))
        self.progress_info.set_text(str(self.exec_status))


class ExecutionInfoWidget(BaseTimedWidgetWrap):

    def __init__(self, execution):
        """
        Widget in charge of showing info related to the execution (except its status)

        Args:
            execution:

        """

        self.execution = execution

        self.max_running_widget = urwid.Text('')
        self.status_widget = urwid.Text('')
        self.update()

        self.widget = urwid.Columns(
            [('weight', 5, self.max_running_widget),
             ('weight', 5, self.status_widget)])

        BaseTimedWidgetWrap.__init__(self, self.widget)

    def __get_status(self):
        return 'Enabled' if self.execution.is_submission_enabled else 'Halted'

    def update(self):
        self.max_running_widget.set_text('Max jobs to cluster: {}'.format(self.execution.max_running))
        self.status_widget.set_text('Jobs submission: {}'.format(self.__get_status()))


class UpdatablePile(urwid.Pile):

    def update(self):
        pass


class ExecutionWidget(BaseTimedWidgetWrap):

    def __init__(self, execution_manager):
        self.execution_manager = execution_manager

        # Create layout

        # Menu layout
        self.menu = urwid.BoxAdapter(None, 20)
        # Menu structure
        self.menu_structure = {
            'main': (None, [('Jobs', self.show_menu, 'jobs'),
                            ('Change max running', self.change_max_running),
                            ('Stop/continue submission', self.show_menu, 'terminate'),
                            ('Resubmit failed', self.resubmit_failed),
                            ('Update metadata files', self.metadata_update),
                            ('Exit', self.show_menu, 'exit')]),
            'jobs': ('main', []),
            'terminate': ('main', [('Stop submission', self.halt),
                                   ('Cancel running and stop submission', self.terminate)]),
            'exit': ('main', [('Submit & exit', self.submit_and_exit), ('Exit', self.exit)])
        }
        # Add the groups
        job_groups = JOB_STATUS_VALUES
        for group in job_groups:
            self.menu_structure['jobs'][1].append((group.title(), self.show_group, group))

        self.previous_menu = None

        # Manager status (progress bar and group counts)
        self.execution_status_widget = ExecutionStatusWidget(self.execution_manager.status)
        # Extra info for the run (max running, running/halted ...)
        self.execution_info_widget = ExecutionInfoWidget(self.execution_manager)

        # Widget that wraps the "changeable" data. Moves from cluster info to job info
        self.details = urwid.Padding(None, align='center', left=2, right=2)  # workaround

        # The cluster widget is only one. The jobs we create them on demand
        self.cluster_widget = ClusterWidget()

        # Initialize empty widgets
        self.show_menu(None, 'main')
        self.details.original_widget = UpdatablePile([self.cluster_widget, ExecutionParameters(self.execution_manager)])

        output_path = urwid.AttrMap(urwid.Text('Out: ' + path.abspath(self.execution_manager.out_folder)), 'folder')

        self.widget = urwid.Filler(urwid.Columns([
            ("fixed", 50, self.menu),
            ("weight", 0.6, urwid.Padding(urwid.Pile([
                output_path,
                urwid.Divider(),
                self.execution_status_widget,
                self.execution_info_widget,
                urwid.Divider(),
                self.details]),
            align='center', left=2, right=2))
        ]))

        BaseTimedWidgetWrap.__init__(self, self.widget)

        # If the execution is halted (due to reattach) update the corresponding widget
        if not self.execution_manager.is_submission_enabled:
            self.halt(None)

    def show_menu(self, _, menu_name):
        """
        Show a menu
        """
        if menu_name in ['main', 'jobs', 'terminate', 'exit']:
            # if the key is in the original ones, ensure that the inner widget is the right one. Done to avoid the inner widget to be the one of a job permanently
            self.details.original_widget = UpdatablePile([self.cluster_widget, ExecutionParameters(self.execution_manager)])

        previous_menu, current_items = self.menu_structure[menu_name]
        menu_items = [urwid.AttrWrap(urwid.Text('QMap'), "menu header"), urwid.Divider()]
        if previous_menu is not None:
            menu_items.append(create_button("go back", self.show_menu, previous_menu))
            menu_items.append(urwid.Divider())
        menu_items += create_buttons_list(current_items)
        self.menu.original_widget = urwid.ListBox(urwid.SimpleFocusListWalker(menu_items))

        self.previous_menu = previous_menu

    def change_max_running(self, _):
        """
        Show the widget to change the maximum running jobs
        """
        current = self.execution_manager.max_running
        self.details.original_widget = IntInputWidget('Maximum jobs running/pending:  ', current, self.__change_max_running)

    def metadata_update(self, _):
        """
        Update metadata of all jobs
        """
        self.details.original_widget = YesNoWidget('Update metadata files?', self.__metadata_update)

    def __back_to_main(self):
        # Go back to main menu
        self.show_menu(None, 'main')
        # Update execution information
        self.update_info()

    def __change_max_running(self, value):
        """
        Callback function to change the value of maximum running jobs
        """
        self.execution_manager.max_running = value
        self.__back_to_main()

    def __metadata_update(self, value):
        """
        Callback function to update the metadata files of the jobs
        """
        if value:
            try:
                self.details.original_widget = TextWidget('Updating metadata files. Please, wait...')
                self.execution_manager.close()
            except QMapError as e:
                self.details.original_widget = TextWidget(e)
        self.__back_to_main()

    def exit(self, _):
        """
        Exit without submitting remaining jobs
        """
        try:
            self.execution_manager.close()
        except QMapError as e:
            print(e)
        raise urwid.ExitMainLoop()

    def submit_and_exit(self, _):
        """
        Submit all jobs and exit
        """
        try:
            self.execution_manager.submit_and_close()
        except QMapError as e:
            print(e)
        raise urwid.ExitMainLoop()

    def terminate(self, _):
        """
        Cancel all running jobs and stop the submission of the remaining ones
        """
        self.execution_manager.terminate()
        self.menu_structure['terminate'] = ('main', [('Continue submitting jobs', self.enable_submission)])
        self.__back_to_main()

    def halt(self, _):
        """
        Stop submitting jobs to the cluster
        """
        self.execution_manager.is_submission_enabled = False
        self.menu_structure['terminate'] = ('main', [('Continue submitting jobs', self.enable_submission)])
        self.__back_to_main()

    def enable_submission(self, _):
        """
        Put the execution in running mode
        """
        self.execution_manager.is_submission_enabled = True
        self.menu_structure['terminate'] = ('main', [('Stop submission', self.halt),
                                                     ('Cancel running and stop submission', self.terminate)])
        self.__back_to_main()

    def resubmit_failed(self, _):
        """
        Resubmit all failed jobs
        """
        self.show_menu(None, 'main')
        try:
            self.execution_manager.resubmit_failed()
            self.update_info()
        except QMapError as e:
            self.update_info()
            self.details.original_widget = TextWidget(e)

    def show_group(self, _, group):
        """
        Create a menu with the all the jobs in one group
        """
        items = []
        for id in self.execution_manager.get_jobs(group):
            job = self.execution_manager.get(id)
            if job.retries > 0:
                items.append(("{}".format(job), self.show_job_details, id, ('retried job', 'retried job select')))
            else:
                items.append(("{}".format(job), self.show_job_details, id))

        menu_key = "Jobs {}".format(group)
        self.menu_structure[menu_key] = ("jobs", items)
        self.show_menu(None, menu_key)

    def show_job_details(self, _, id_):
        """
        Create a menu with the job functions
        and show the job information
        """
        job = self.execution_manager.get(id_)
        if job is not None:
            self.details.original_widget = JobWidget(job)  # use the job widget as the inner widget

    def update_info(self):
        """
        Update the general information and call the inner widget update method.
        """
        self.execution_status_widget.update()
        self.execution_info_widget.update()
        self.cluster_widget.update()  # update the cluster info even if it is not being displayed
        self.details.original_widget.update()

    def update(self, loop=None, user_data=5):
        """
        Update the execution and corresponding information

        Args:
            loop:
            user_data:

        """
        self.execution_manager.update()
        self.update_info()
        if self.execution_manager.is_done:
            if TIMER.is_running and TIMER.is_done:
                raise StopIteration
            elif not TIMER.is_running:
                TIMER.is_running = True
                TIMER.reset()
        else:
            Timer.is_running = False
        if loop is not None:
            loop.set_alarm_in(user_data, self.update, user_data=user_data)

    def unhandled(self, key):
        """
        Use F8 to show the exit menu
        """
        if key == 'f10':
            self.show_menu(None, 'exit')
        elif key == 'backspace':
            if self.previous_menu is None:  # from main menu go to exit menu
                self.show_menu(None, 'exit')
            else:
                self.show_menu(None, self.previous_menu)


def run(manager, update_period=5, inactivity_period=30*60):
    global PARAMS, TIMER
    PARAMS = manager.editable_job_params
    TIMER = Timer(inactivity_period)
    widget = ExecutionWidget(manager)
    screen = urwid.raw_display.Screen()  # default library screen
    loop = urwid.MainLoop(widget, palette=PALETTE, screen=screen, unhandled_input=widget.unhandled)
    widget.update(loop, update_period)
    try:
        loop.run()
    except (KeyboardInterrupt, StopIteration):
        try:
            widget.exit(None)
        except urwid.ExitMainLoop:
            pass
    print(manager.status)
    print('Logs directory: {}'.format(manager.out_folder))
