# Nix Made Containers For Newbies

In this article, I will try to explain in detail how to create a (Docker)
container for a small python server that I want to run. Since I am a Nix newbie
and I am still learning the basics, I will take some time to go in detail, but I
assume you know a few things:
 - what is nix (the package manager),
 - that nix is also a language (I will review some of it),
 - what is nixpkgs (the collection of packages).

Enough with the intro, let's dive in.

## Having one objective

First, let's build the python application: it is a very simple starlette server
that answers with a JSON payload whenever we GET /. I won't go into details of
this code as I want to focus on nix, not python.

This is the source code of `server.py`

```python3
#!/usr/bin/env python3
import logging
import uvicorn

from starlette.applications import Starlette
from starlette.responses import JSONResponse


app = Starlette(debug=True)


@app.route("/", methods=["GET"])
async def homepage(request):
    logging.info("Got a request")
    return JSONResponse({
        "message": "Hello, World!",
    })


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

We can test this easily with a nix shell:

```
nix-shell -p python38Packages.starlette python38Packages.uvicorn \
          --run "python3 server.py"
```

This command will get the packages `python38Packages.startlette` and
`python38Packages.uvicorn` from my current nixpkgs, then run `python3 server.py`
which will start the server on port 8000. We can see the server working by doing

```
$ curl 127.0.0.1:8000
{"message":"Hello, World!"}
```

The `nix-shell` command is basically getting the requested packages from nixpkgs
and ensuring they are available on the system: it will download missing packages
and create a shell where those packages and their dependencies are available.
In this case, since I am using the `--run` flag to specify a single command to
run, the shell is not interactive and will quit once the server is terminated,
otherwise one would get a new shell properly configured to interact with those
packages.

Please note that nix is taking care of inserting the packages path in the
`PYTHONPATH` variable, meaning that python is properly configured for using
those packages.

Well, we basically to containerize what we just did. That is our objective.

## A useless container for podman

Now, I want to create a dummy container to get acquainted with the tools. I will
build a Docker image using nix, a binary blob that can be loaded in a runtime
and be used as an image to run new containers.

**Side note**
Even if I will build a Docker image, I will use [podman](https://podman.io/) as
a runtime to build containers from that image. This is just because I prefer
podman over Docker for a few reasons (e.g. daemonless + rootless by default),
but this will have no impact in this article: whenever you read `podman`, you
can replace it with `docker` as they are compatible on the command line for what
we are going to do here. "Docker image", in this case, means "an image in the
Docker format", which `podman` can use just fine.

Now let's write a nix file with the code needed to build that image. This is the
content of the `default.nix` file in the same directory of `server.py`:

```nix
{ pkgs ? import <nixpkgs> { } }:
with pkgs:
dockerTools.buildImage {
  name = "dummy";
  tag = "latest";
  created = "now";
  contents = [
    busybox
  ];
  config.Cmd = [ "sh" ];
}
```

### The container workflow

We can then build the image using `nix-build`: nix will download the
dependencies and build the image, placing the results somewhere in the nix store
(the directory on the system that contains all the nix packages) and linking it
in the current directory.

```bash
$ nix-build
these derivations will be built:
  /nix/store/c9rigfy5zdaw439qjgxzw7bx9vn71l7c-dummy-config.json.drv
... et cetera ...
Cooking the image...
Finished.
/nix/store/d9a5d9im5h2mbs3ncv60p0y7j8fw2n6m-docker-image-dummy.tar.gz

$ ls -l
total 16
-rw-r--r-- 1 akiross akiross  182 Jul  3 12:21 default.nix
-rw-r--r-- 1 akiross akiross 3506 Jul  3 12:21 README.md
lrwxrwxrwx 1 akiross akiross   69 Jul  3 12:21 result -> /nix/store/d9a5d9im5h2mbs3ncv60p0y7j8fw2n6m-docker-image-dummy.tar.gz
-rw-r--r-- 1 akiross akiross  439 Jul  3 11:56 server.py

$ file `readlink result`
/nix/store/d9a5d9im5h2mbs3ncv60p0y7j8fw2n6m-docker-image-dummy.tar.gz: gzip compressed data
```

The `result` is a symbolic link to the actual image built, which is a gzipped
tar file containing the Docker image. We can now load that in podman and run a
container:

```bash
$ podman load < result
Getting image source signatures
... et cetera ...
Loaded image(s): localhost/dummy:latest

$ podman run -it --rm localhost/dummy
/ # ls
bin             dev             linuxrc         proc            sbin
default.script  etc             nix             run             sys
/ # exit
```

As you can see, we just loaded the image and run a container using it, and we
can get our `busybox` environment pretty easily.

Ok, this was the general workflow we are adopting. Now, let's dive in the nix
expression that I wrote above to understand what is going on and break it down.

### Breaking down the nix expression

Before starting, note that we can use `nix repl` to run code interactively:

```bash
$ nix repl
Welcome to Nix version 2.3.12. Type :? for help.

nix-repl>
```

I will use `nix-repl>` as a prefix in my code to show the interactive execution
of nix expressions.

<details>
<summary>Nix language: functions</summary>
Nix is a functional language, so let's get to know functions better! A function
in `nix` language is defined as `param: body`, where `param` is a single
parameter and `body` is an expression where `param` might appear.
A function is called by writing a the parameter value after the function,
separated by a single space. For example:

```
nix-repl> v: v 123
123
```

defines the identity function `v: v` that takes a parameter `v` and returns it.
This function is written in `()` so we can call it immediately, passing 123 as
argument and getting back the same value. We need to put the function in
parentheses because that function has no name, otherwise we could have called
it like

```
nix-repl> identity_function 123
123
```

Another example:
```
nix-repl> (name: "Hello " + name) "World!"
"Hello World!"

```

similarly to above, the function is `name: "Hello " + name` which takes a single
parameter and returns the string `"Hello "` concatenated with the parameter
(which has to be a string, btw). The function, put in parentheses, is then
called passing the `"World!"` string as argument.

It is not possible to pass multiple arguments to a single function: what we can
do is to either

 - pass a single argument which is a collection of objects, or
 - pass the first argument and get back a function that takes another argument.

The second method is known as [currying](https://en.wikipedia.org/wiki/Currying)
and it goes like this:

```
nix-repl> (greet: name: greet + " " + name) "Hello" "World"
"Hello World"
```

This can be written more clearly (but verbosely) as:

```
nix-repl> ((greet: (name: (greet + " " + name))) "Hello") "World"
"Hello World"
```

which should make clear that there are actually two functions involved and
that we are calling the first one `greet: ...` passing `"Hello"`, which will
return a function equivalent to `name: "Hello" + " " + name`.

More often, you will see a collection passed to a function, that is, a bunch
of different data grouped in a structure. The nix language has lists and sets
(a.k.a. dictionaries/maps/attribute sets/associative arrays) to group multiple
values in a single expression. We can use those, for example:

```
nix-repl> [ "World" "Universe" ]
[ "World" "Universe" ]
```

is a list with two elements, separated by spaces. We can get an element using
the `builtins.elemAt` function, which uses currying:

```
nix-repl> builtins.elemAt [ "World" "Universe" ] 1
"Universe"
nix-repl> (names: "Hello " + (builtins.elemAt names 0) + " from " + (builtins.elemAt names 1)) [ "World" "Universe" ]
"Hello World from Universe"
```

As said, there are not just lists, but also sets:

```
nix-repl> { name = "World"; place = "Universe"; }.place
"Universe"
```

sets are built using `{}` and specifying pairs of attribute-value. Note that
each pair must be followed by `;` as a separator. The dot `.` can be used to
retrieve the value of a specific attribute in the set - `place` in this case.

We can use those in functions of course:

```
nix-repl> (v: "Hello " + v.name + " from " + v.place) { name = "World"; place = "Universe"; }
"Hello World from Universe
```

This works, but there's something better: nix allows to do pattern matching over
sets as arguments, allowing to bind the relevant values of the set passed as
argument (note attributes are separated by commas, not semi-colons):

```
nix-repl> ({ name, place }: "Hello " + name + " from " + place) { name = "World"; place = "Universe"; }
"Hello World from Universe"
```

Two more things to know before going back to building containers.

First, if the argument set contains more keys, nix will fail
(because some attributes are not matched), but it's possible to use `...` in the
pattern to signal that more values might be present.

```
nix-repl> ({ name, place }: "Hello " + name + " from " + place) { name = "World"; place = "Universe"; foo = "Bar"; }
error: anonymous function at (string):1:2 called with unexpected argument 'foo', at (string):1:1

nix-repl> ({ name, place, ... }: "Hello " + name + " from " + place) { name = "World"; place = "Universe"; foo = "Bar"; }
"Hello World from Universe"
```

Note we added a `foo` attribute in the argument set, and used `...` in the
latter example.

Second, that it is possible to use default values in the argument attributes
when they are missing in the argument:

```
nix-repl> ({ name, place ? "Universe", ... }: "Hello " + name + " from " + place) { name = "World"; foo = "Bar"; }
"Hello World from Universe"
```

Note that we used `place ? "Universe"` and `place` was missing from the set.

Finally, `let` expressions might come handy, so let me explain them here.
They are a way to bind values to names and reference the values by their names,
at least inside a certain body. The expression body will be evaluated and that
is the value assumed by the expression. The syntax is:

```
let <bindings> in <body>
```

where `<bindings>` is a sequence of `<name> = <value>;` and `<body>` is an
expression where `<name>s` will be in scope.

A couple of examples:

```
nix-repl> let a = 1; b = 2; in a + b
3

nix-repl> let
            args = { name = "World"; foo = "Bar"; };
            func = { name, place ? "Universe", ... }: "Hello " + name + " from " + place;
          in
            func args
"Hello World from Universe"
```

In the second example, we could make the example above a bit more clear: now
you can see easily what is a function and what are the arguments, without having
to write everything between `()`.

Whew! That was a lot to chew, but things should be clearer now.
</details>

Let's break down the original expression:

```nix
{ pkgs ? import <nixpkgs> { } }:
with pkgs:
dockerTools.buildImage {
  name = "dummy";
  tag = "latest";
  created = "now";
  contents = [
    busybox
  ];
  config.Cmd = [ "sh" ];
}
```

Now, you should know that when running `nix-build`, nix will look for a file
`default.nix` and will try evaluate that. `nix-build` needs a **derivation** to
build, which is basically a file containing the instructions for a reproducible
build of something. In this example, `default.nix` evaluates to a function that,
when called, returns a derivation that `nix-build` can use to actually builds
the image.

<details>
<summary>What is a derivation?</summary>
The derivation is just a file, btw, identified by its path. When we launched
`nix-build` before, the output was actually the following:

```
these derivations will be built:
  /nix/store/c9rigfy5zdaw439qjgxzw7bx9vn71l7c-dummy-config.json.drv
  /nix/store/1nb30zbq8gyl1hc2i5ji6hdmg21p2vxd-dummy-config.json.drv
  /nix/store/j7934rzrlqra5rdf2iif9537ahyrm1x0-docker-layer-dummy.drv
  /nix/store/fh2c9yjg1in2zjcs2f7siq3qhckyph2q-runtime-deps.drv
  /nix/store/3y01yb1d81n4mff5p2ammzrxp19jw6ws-docker-image-dummy.tar.gz.drv
building '/nix/store/c9rigfy5zdaw439qjgxzw7bx9vn71l7c-dummy-config.json.drv'...
building '/nix/store/1nb30zbq8gyl1hc2i5ji6hdmg21p2vxd-dummy-config.json.drv'...
building '/nix/store/j7934rzrlqra5rdf2iif9537ahyrm1x0-docker-layer-dummy.drv'...
Adding contents...
Adding /nix/store/5havwmdc9q054i1f6yjdxjbldiv2vvjh-busybox-1.32.1
Packing layer...
Finished building layer 'dummy'
building '/nix/store/fh2c9yjg1in2zjcs2f7siq3qhckyph2q-runtime-deps.drv'...
building '/nix/store/3y01yb1d81n4mff5p2ammzrxp19jw6ws-docker-image-dummy.tar.gz.drv'...
Adding layer...
tar: Removing leading `/' from member names
Adding meta...
Cooking the image...
Finished.
/nix/store/d9a5d9im5h2mbs3ncv60p0y7j8fw2n6m-docker-image-dummy.tar.gz
```

At the top, you can see a list of derivations to be built, some are intermediate
and one is the one resulting from that function. We can see its content:

```
cat /nix/store/3y01yb1d81n4mff5p2ammzrxp19jw6ws-docker-image-dummy.tar.gz.drv
Derive([("out","/nix/store/d9a5d9im5h2mbs3ncv60p0y7j8fw2n6m-docker-image-...
...ystem","x86_64-linux")])%
```

That's a bunch of stuff that is meant to be processed by nix to build packages
and containers. We don't need to understand that, but feel free to read it if
you want. You might be interested in `nix show-derivation` in that case.
</details>

`{ pkgs ? <snip> }: <snip>` is the top-level element in the expression. It is a
function which takes a set as argument containing `pkgs`.

If `pkgs` is missing, `import <nixpkgs> { }` will be used as a value, which is
a function that will load a path to a nix source file, evaluates it and return
its value. The `{ }` is an optional list of arguments that will be used when
evaluating the file expression. `<nixpkgs>` is a special value that contains
the path of the default nixpkgs in use in the system:

```
nix-repl> <nixpkgs>
/nix/var/nix/profiles/per-user/root/channels/nixos
```

So, we have now
```nix
{ pkgs ? import <nixpkgs> { } }:
with pkgs;
<body>
```

The `with <set>; <body>` syntax means that we put the attribute of `<set>` in
the scope of `<body>` - basically allowing us to type `attribute` instead of
`set.attribute`:

```
nix-repl> with { name = "World"; }; name
"World"

nix-repl> let data = { name = "World"; place = "Universe"; };
          in with data;
          name + ", " + place
"World, Universe"
```

In our `default.nix`, the body of `with` expression is

```nix
dockerTools.buildImage {
  name = "dummy";
  tag = "latest";
  created = "now";
  contents = [
    busybox
  ];
  config.Cmd = [ "sh" ];
}
```

which is a function call: `pkgs.dockerTool.buildImage` with a set as argument.

Referring to the [nixpkgs manual](https://nixos.org/manual/nixpkgs/stable/#ssec-pkgs-dockerTools-buildImage)
we can read the meaning of those attributes:

 - *name*: the name of the resulting image;
 - *tag*: the tag of the image - `latest` in this case, an a hash otherwise;
 - *created*: if not specified, the image is built in a reproducible environment
   which sets the image creation date at the Unix epoch, 1st Jan 1970;
 - *contents*: the derivation copied in the resulting image;
 - *config*: a set with configuration of the Docker image, according to the
   [Docker Image Specification](https://github.com/moby/moby/blob/master/image/spec/v1.2.md#image-json-field-descriptions);

The values should be pretty self-explanatory: the image named `dummy` will
contain `busybox` and container will execute `sh` command by default when run.

## Let's get the python tools ready!

Ok, that's all great and dandy and we managed to copy things from the nix store
to the container. We can happily get busybox and redis in our image, but what
about our python dependencies?

Let's fix the dependencies first. We want to get the same packages used in the
`nix-shell` at the beginning: `python38Packages.<etc>`.

That should be easy to do, so let's adjust our `default.nix` file for that
(and let's drop the `dummy` name now, since we are actually getting ready for
the server):

```nix
{ pkgs ? import <nixpkgs> {} }:
with pkgs;
dockerTools.buildImage {
  name = "my_server";
  tag = "latest";
  created = "now";
  contents = [
    python38  # what if we leave this out?
    python38Packages.starlette
    python38Packages.uvicorn
  ];
  config.Cmd = [ "python3" ];
}
```

Let's get it running:

```
$ nix-build
these derivations will be built:
...
Finished.
/nix/store/n3s1558irxsx7z6y6pp08hxdgqyxpwn4-docker-image-my_server.tar.gz

$ podman load < result
Getting image source signatures
...
Loaded image(s): localhost/my_server:latest

$ podman run -it --rm localhost/my_server
Python 3.8.9 (default, Apr  2 2021, 11:20:07)
[GCC 10.3.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> import starlette
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ModuleNotFoundError: No module named 'starlette'
>>>
```

WAT. It worked in `nix-shell`! Why is `starlette` not reachable?

The problem here is that even if packages were copied into the image, it was not
configured to use them together: while python applications have all the needed
setup to run properly and use their dependencies, python libraries (such as
uvicorn and starlette) are not bundled together, since they are individual
components usable in multiple places and in different ways.

This is explained in more detail in the
[nixpkgs manual's python section](https://nixos.org/manual/nixpkgs/stable/#python)

> But Python libraries you would like to use for development cannot be
> installed, at least not individually, because they won’t be able to find each
> other resulting in import errors. Instead, it is possible to create an
> environment with python.buildEnv or python.withPackages where the interpreter
> and other executables are wrapped to be able to find each other and
> all of the modules.

So we need to build an environment for python, similar to the one that python
applications are using, so that libraries can be discovered. This can be done
easily with the following:

```nix
{ pkgs ? import <nixpkgs> {} }:
with pkgs;
let 
  my_program = python38.withPackages (ps: [
    ps.starlette
    ps.uvicorn
  ]);
in
dockerTools.buildImage {
  name = "my_server";
  tag = "latest";
  created = "now";
  contents = [ my_program ];
  config.Cmd = [ "python3" ];
}
```

We used a `let` expression to create an environment and give it the name
`my_program`: that environment, where libraries and executables are able to
see each other, is then placed in the `contents` of the container.

```
$ nix-build && podman load < result && podman run -it --rm localhost/my_server
these derivations will be built:
...
Python 3.8.9 (default, Apr  2 2021, 11:20:07)
[GCC 10.3.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> import uvicorn
>>> import starlette
```

As you can see, `uvicorn` and `starlette` are in path now, so our application
is able to load them. Noice!

## Pulling in the code

The last required step is to actually run the python code defined above.
We have the tools, but where's the code? If we look at the busybox example above
we can tell that code was not copied inside the image.

This is fine and differently from Dockerfiles where you would use `COPY` and
`ADD` to bring code in, we can actually include it in the `my_program`
derivation - as if it was an actual python program in `nixpkgs`. The only
difference would be that, instead of getting the derivation from an existing
expression in `nixpkgs`, we are going to build the expression manually for that
program and then include it in the container as we saw above.

Again, the nixpkgs manual will is helpful here: while `python38.withPackages` is
great to create a development environment, that is not enough to create a
python application.

> With Nix all packages are built by functions. The main function in Nix
> for building Python libraries is `buildPythonPackage`.

and

> The `buildPythonApplication` function is practically the same as
> `buildPythonPackage`. The main purpose of this function is to build a Python
> package where one is interested only in the executables, and not
> importable modules

In this case we want to build a python application, since we intend to run it
in the container. You can take a loop at [the wiki](https://nixos.wiki/wiki/Python)
for more info about packaging python libraries and applications.

That function can be found (e.g. [using manix or nix-doc](https://jade.fyi/blog/finding-functions-in-nixpkgs/))
in `pkgs.python38Packages.buildPythonApplication`. That function relies on the
`setup.py` file commonly used in python packages. So, we can do things properly
and create it:

```python
# setup.py
#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="my_server",
    version="0.0.1",
    packages=find_packages(),
    scripts=["server.py"],
)
```

and have our `default.nix` as following

```nix
{ pkgs ? import <nixpkgs> {} }:
with pkgs;
let
  my_program = with python38Packages; buildPythonApplication {
    pname = "my_server";
    version = "0.0.1";
    propagatedBuildInputs = [ uvicorn starlette ];
    src = ./.;
  };
in
dockerTools.buildImage {
  name = "my_server";
  tag = "latest";
  created = "now";
  contents = [ my_program ];
  config.Cmd = [ "${my_program}/bin/server.py" ];
}
```

`my_program` is the result of calling the `python38Packages.buildPythonApplication`
function, which describes the program name, its version and the runtime
requirements (`propagatedBuildInputs` is used for dependencies that are both
build-time and run-time, while `buildInputs` is only for build-time ones).
In this case, uvicorn and starlette are needed at runtime.

Here, `${my_program}` is expanded to the path of the `my_program` derivation,
which is unique in the nix store, and the server file will be found under
the `bin` directory.

Then, we specify that `my_program` needs to be part of the container content, as
we did earlier, but we also need to change the command being run: in this case,
it is the script itself, which will be made executable and has a hashbang
in the first line, so it uses the correct interpreter:

```python
#!/usr/bin/env python3
```

If we do all the steps, we get the server up and running, yay!

```
$ nix-build && podman load < result && podman run -it --rm localhost/my_server
these derivations will be built:
<cut>
INFO:uvicorn.error:Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Bonus!

Now that we completed all the steps to get the container working, I will add
a bonus that might be useful in future: the function output does not need to be
a single derivation, but also a dictionary of derivations. That is useful if,
for example, we want to test our application without going through all the steps
to build an image and then run a container.

Consider this `default.nix`:

```nix
{ pkgs ? import <nixpkgs> { } }:
{
  foo = blahblah;
  bar = blahblah;
}
```

we can then build only one of the attributes using `nix-build -A foo` or
`nix-build -A bar`. The `-A` option specifies an attribute path.

This comes handy in our case, so we can adjust our expression to be like:

```nix
{ pkgs ? import <nixpkgs> {} }:
with pkgs;
let
  my_program = with python38Packages; buildPythonApplication {
    pname = "my_server";
    version = "0.0.1";
    propagatedBuildInputs = [ uvicorn starlette ];
    src = ./.;
  };
in {
  server = my_program;

  image = dockerTools.buildImage {
    name = "my_server";
    tag = "latest";
    created = "now";
    contents = [ my_program ];
    config.Cmd = [ "${my_program}/bin/server.py" ];
  };
}
```

And we can test that the application is working by doing

```
$ nix-build -A server
...
$ ./result/bin/server.py
INFO:     Started server process [39380]
...
```

and build the image with `nix-build -A image`.

I hope you enjoyed this article!

# References

Some additional material, if you want to go in detail.

About building containers with nix:

- https://nixos.org/manual/nixpkgs/stable/#ssec-pkgs-dockerTools-buildImage
- http://lethalman.blogspot.com/2016/04/cheap-docker-images-with-nix_15.html
- https://jamey.thesharps.us/2021/02/02/docker-containers-nix/
- http://datakurre.pandala.org/2015/07/building-docker-containers-from-scratch.html/
- https://yann.hodique.info/blog/using-nix-to-build-docker-images/
- https://thewagner.net/blog/2021/02/25/building-container-images-with-nix/

Creating python applications:

 - https://jade.fyi/blog/finding-functions-in-nixpkgs/

Something more on the nix language:

 - https://medium.com/@MrJamesFisher/nix-by-example-a0063a1a4c55
