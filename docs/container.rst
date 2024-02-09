==============================
Using heudiconv in a Container
==============================

If heudiconv is :ref:`installed via a Docker container <install_container>`, you
can run the commands in the following format::
   
    docker run nipy/heudiconv:latest [heudiconv options]

So a user running via container would check the version with this command::

    docker run nipy/heudiconv:latest --version

Which is equivalent to the locally installed command::

    heudiconv --version

Bind mount
----------

Typically, users of heudiconv will be operating on data that is on their local machine. We can give heudiconv access to that data via a ``bind mount``, which is the ``-v`` syntax.

Once common pattern is to share the working directory with ``-v $PWD:$PWD``, so heudiconv will behave as though it is installed on your system. However, you should be aware of how permissions work depending on your container toolset.


Docker Permissions
******************

When you run a container with docker without specifying a user, it will be run as root.
This isn't ideal if you are operating on data owned by your local user, so for ``Docker`` it is recommended to specify that the container will run as your user.::

    docker run --user=$(id -u):$(id -g) -e "UID=$(id -u)" -e "GID=$(id -g)" --rm -t -v $PWD:$PWD nipy/heudiconv:latest --version

Podman Permissions
******************

When running Podman without specifying a user, the container is run as root inside the container, but your user outside of the container.
This default behavior usually works for heudiconv users::

    docker run -v $PWD:PWD nipy/heudiconv:latest --version

Other Common Options
--------------------

We typically recommend users make use of the following flags to Docker and Podman

* ``-it`` Interactive terminal
* ``--rm`` Remove the changes to the container when it completes

