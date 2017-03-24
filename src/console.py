# https://gist.githubusercontent.com/rduplain/899f6a5e583a85668822/raw/bd54028bbf3d137a97f3711437e9931272495503/console.py
import code
import shlex
import sys
from clint.textui import colored, puts, indent
from sys import stderr


class CommandRunner(object):
    "Simple demo."
    def __init__(self):
        self.commands = {}
        self.command('help', self.cmd_help)

    def command(self, name, fn):
        self.commands[name] = fn

    def cmd_help(self, *args):
        'List all commands and a short description'
        return '\n'.join( [ '{}\t-\t{}'.format(nm, fn.__doc__) for nm, fn in self.commands.items() ] )

    def run(self, line):
        tokens = shlex.split(line, comments=True)
        try:
            command, args = tokens[0], tokens[1:]
        except IndexError:
            return
        if command not in self.commands:
            print('{}: no such command'.format(command), file=stderr)
            return
        try:
            result = self.commands[command](*args)
            if result is not None:
                puts(colored.magenta(result))
        except TypeError as e:
            raise
            puts(colored.red(str(e)))


class Console(object):
    ps1 = '> '
    ps2 = '. '

    def __init__(self, runner):
        self.runner = runner

    def run(self, fd):
        for line in fd:
            self.runner.run(line)

    def interact(self, locals=None):
        class LambdaConsole(code.InteractiveConsole):
            def runsource(code_console, source, filename=None, symbol=None):
                # Return True if more input needed, else False.
                try:
                    self.runner.run(source)
                except SystemExit:
                    raise
                except:
                    code_console.showtraceback()
                return False

        # import readline to support line editing within console session.
        try:
            import readline; readline
        except ImportError:
            pass

        # Patch ps1 & ps2 for interaction. Note sys.psX may be unset.
        ps1, ps2 = getattr(sys, 'ps1', None), getattr(sys, 'ps2', None)
        try:
            sys.ps1, sys.ps2 = self.ps1, self.ps2
            LambdaConsole(locals=locals, filename="<demo>").interact(banner='')
        finally:
            sys.ps1, sys.ps2 = ps1, ps2

    def run_in_main(self, fd=None, interact=False):
        if fd is None:
            fd = sys.stdin
        if fd.isatty():
            self.interact()
        else:
            try:
                self.run(fd=fd)
            except Exception as err:
                print(err, file=stderr)
                return 1
        return 0


class Room(object):
    "Simple demo."

    def __init__(self):
        self.people = set()

    def enter(self, *people):
        for person in people:
            if person in self.people:
                print('{} is already in the room.'.format(person), file=stderr)
            else:
                print('{} enters the room.'.format(person))
                self.people.add(person)

    def exit(self, *people):
        for person in people:
            if person in self.people:
                print('{} leaves the room.'.format(person))
                self.people.remove(person)
            else:
                print('{} is not in the room.'.format(person), file=stderr)

    def room(self):
        if self.people:
            print('In the room: {}'.format(', '.join(self.people)))
        else:
            print('No one is in the room.')


def main(fd=None):
    room = Room()
    runner = CommandRunner()
    runner.command('enter', room.enter)
    runner.command('exit', room.exit)
    runner.command('room', room.room)
    return Console(runner).run_in_main(fd)


if __name__ == '__main__':
    sys.exit(main())

