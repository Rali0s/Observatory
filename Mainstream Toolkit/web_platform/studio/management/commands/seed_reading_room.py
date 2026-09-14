"""Install original, clearly labeled demo readings without touching private work."""
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from studio.models import AuthorProfile, Publication
from studio.taxonomy import apply_tags


READINGS = [
    ('mara', 'Mara Finch', 'The House That Kept the Rain', 'story',
     'Every house on Bellweather Lane dried by morning. Number nineteen kept its rain until someone came home.',
     '''On the day we sold my mother's house, it rained in the upstairs bathroom. Outside, the sky was clear. The estate agent opened an umbrella beneath the ceiling and said old properties had their peculiarities.

I put a saucepan under the light fitting. My mother had always used the blue one for this, but I had packed it already.

The buyers arrived at eleven. They admired the floorboards, the garden, the window where the pear tree pressed its leaves against the glass. Nobody went upstairs. From the hallway, the water sounded like somebody counting loose change.

“We'll take it,” the woman said.

Her little boy was sitting on the bottom step. He had removed his shoes and arranged them beside mine.

“Who is crying?” he asked.

“The pipes,” I said.

He considered this, then went into the kitchen. When he returned he was carrying a glass of water. He set it on the stair, carefully, with both hands.

“In case they're thirsty.”

The counting stopped.

For a moment I could hear everything else: a delivery van outside, the agent's pen scratching paper, a pear falling softly into the long grass.

I unpacked the blue saucepan before I left. I told the woman it belonged to the house. She didn't ask why.

On the pavement I looked back. The boy stood in the upstairs window, waving with the whole of his arm. Behind him, sunlight lay on the bathroom tiles.'''),
    ('elias', 'Elias Rowan', 'Instructions for Leaving a Light On', 'poetry',
     'A small poem about the ordinary ways we make a place for someone to return.',
     '''Choose the lamp with the crooked shade.
The good one makes the room
look ready for a stranger.

Leave a book face down,
but not the last page.
Let something remain
to be told.

The cup beside the sink
need not be washed tonight.
There is a kind of welcome
in an unfinished chore.

When the road goes quiet,
resist the window.
Sit where your own reflection
cannot keep you company.

And if they arrive after sleep
has loosened your hands,
let the floorboard speak first.

It has been practicing
their name
all winter.'''),
    ('june', 'June Vale', 'The Last Train to North Orchard', 'chapter',
     'Chapter one: a station clerk receives a ticket for a railway line that disappeared forty years ago.',
     '''The passenger slid the ticket beneath the glass at 6:14, one minute before I closed the station.

“Single or return?” I asked, because twenty-three years behind a counter will put words in your mouth before sense can stop them.

“That's what I've come to find out.”

The ticket was green card, punched twice along its lower edge. NORTH ORCHARD, it said. My father had worked that line. The tracks were lifted the summer we buried him.

“Where did you get this?”

The passenger looked over his shoulder. Platform two was empty except for a pigeon studying a sandwich wrapper.

“You sold it to me.”

I turned the ticket over. There was my employee number, stamped beneath a date forty years earlier than my first shift. Beside it, in handwriting I had not seen since childhood, were three words.

Don't bring luggage.

The departure board clicked. Every evening it clicked at 6:15, clearing the day's last service. This time a new destination appeared.

NORTH ORCHARD. PLATFORM TWO. ON TIME.

The passenger picked up his hat.

“You can stay here,” he said. “I did, the first time.”

I thought of the flat above the chemist, the one clean plate in its rack, the television turning itself off after four hours because nobody had touched the remote.

Then I thought of my father coming home with soot in the creases of his hands, lifting me high enough to see inside his cap.

I left the station keys on the counter.

For the first time in twenty-three years, I did not lock the door.'''),
    ('mara', 'Mara Finch', 'A Table for Two, Eventually', 'excerpt',
     'At a seaside café, an unfinished chess game becomes a conversation between strangers.',
     '''The old man left a chessboard on the café table every Tuesday. One move made, one coffee cooling. By noon he was gone.

On the fourth Tuesday, Nell moved a pawn.

She regretted it immediately. The board might have been a memorial. It might have been the exact position of a famous game. She spent the afternoon wiping an already clean counter and waiting to be told she had ruined something.

The following week, a black knight stood on a different square. Beside the board lay a folded receipt.

Your move.

They played through March. Nell learned that the old man preferred his bishops, that he became reckless near the end of a game, and that he always left the little wrapped biscuit untouched. He learned, presumably, that she was bad at chess.

In April, she wrote beneath his message: You could teach me.

The reply arrived the next Tuesday.

You could sit down.

She brought two coffees. For a while neither of them touched the pieces. Beyond the window, the tide moved around the harbor wall with the patience of something that had never once been late.'''),
    ('elias', 'Elias Rowan', 'What the Garden Returns', 'poetry',
     'After a long absence, the garden has kept growing without asking for an explanation.',
     '''The gate has learned a lower note.
The path has lost its argument
with grass.

Where I planted beans,
something yellow
has made other arrangements.

I came prepared to kneel,
to pull, to cut,
to restore the little order
I mistook for care.

Instead I find a pear
warm on the wall,
its bruised side turned
discreetly toward the stone.

Nothing here asks
where I have been.

I eat standing up.
I leave the gate open.'''),
    ('june', 'June Vale', 'The Mapmaker’s Missing Street', 'story',
     'A cartographer discovers a street that appears only on maps drawn from memory.',
     '''Three people drew the same street for Ada in one afternoon. None of them could tell her where it was.

The baker placed it behind the courthouse. The bus driver put it near the river. A girl in a red coat drew it through the middle of the hospital, then apologized to the hospital.

All three included a bench, a narrow tree, and a shop with no sign.

Ada had mapped the city for twelve years. She knew its service alleys and buried streams, the staircase that counted as a road, the road that ended in somebody's kitchen. She took the three drawings home and laid them on her desk.

Her husband looked at them over her shoulder.

“I bought your birthday present there,” he said.

“Where?”

He pointed at the shop with no sign. Then his expression changed.

“I don't know.”

In the morning Ada left her surveying equipment at home. She walked until she stopped recognizing the route, then walked a little farther. Between a laundrette and a boarded cinema, she found the tree.

The shop sold things people had meant to say. They stood in plain jars on wooden shelves. Ada recognized an apology she had rehearsed for her sister. Beside it was a question her father had died before she could ask.

“Can I take them?” she said.

The shopkeeper shook her head. “Only say them.”

Ada called her sister from the bench. She stayed there until the streetlights came on.

Later, she opened the city map and took up her pen. In the narrow space between the laundrette and the cinema, she drew a tree. Nothing more.

There were places, she decided, that people ought to find by getting a little lost.'''),
]


class Command(BaseCommand):
    help = 'Add six original demo readings and three inactive demo authors; safe to repeat.'

    @transaction.atomic
    def handle(self, *args, **options):
        added = 0
        for slug, name, title, kind, excerpt, body in READINGS:
            user, created = get_user_model().objects.get_or_create(
                username=f'novel_tools_demo_{slug}', defaults={'is_active': False})
            if created:
                user.set_unusable_password()
                user.save(update_fields=['password'])
            elif user.is_active or user.has_usable_password():
                raise CommandError('Demo username belongs to a login-enabled account; nothing was changed.')
            author, _ = AuthorProfile.objects.get_or_create(user=user, defaults={
                'pen_name': f'{name} · Demo',
                'bio': 'Fictional demonstration author. Original AI-generated sample writing for the Novel Tools Reading Room; not a real member.'})
            publication, created = Publication.objects.get_or_create(
                id=uuid5(NAMESPACE_URL, f'novel-tools:reading-room-demo:{slug}:{title}'),
                defaults={'author': author, 'title': title, 'kind': kind, 'excerpt': excerpt,
                          'body': body + '\n\n—\nDemo reading · Original AI-generated sample fiction for Novel Tools.'})
            if created:
                publication.channel = 'poetry' if kind == 'poetry' else 'mystery' if slug == 'june' else 'fiction'
                publication.save(update_fields=['channel'])
                apply_tags(publication, 'poetry nature' if kind == 'poetry' else 'mystery magical-realism' if slug == 'june' else 'literary quiet-fiction')
            added += created
        self.stdout.write(self.style.SUCCESS(f'Added {added} demo readings. Existing publications and private drafts were preserved.'))
