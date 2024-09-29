#### Importações necessárias 
import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Select
import asyncio
from datetime import datetime

### Declara as intenções do bot
intents = discord.Intents.default()
intents.members = True
intents.presences = True 
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

### Config de canais, categorias, imagens e cargos
PANEL_IMAGE_URL = ''
DISCORD_IMAGE_URL = ''

LOG_CHANNEL_ID_allowlist = 123
FORM_CHANNEL_ID = 123
CATEGORY_NAME = "📑・Entrada"

REFAZER_ROLE_ID = 123
SEM_WL_ROLE_ID = 123
ENTREVISTA_ROLE_ID = 123
REPROVADO_ROLE_ID = 123

### Lista para guardar repostas e mensagens dos usuários
user_responses = {}
user_messages = {}

### Funções e classes
def formatar_data(data):
    try:
        return datetime.strptime(data, '%d/%m/%Y').strftime('%d/%m/%Y')
    except ValueError:
        raise ValueError("Data no formato inválido")

class StartWhitelistButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="📑 Iniciar Allowlist")

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message("Erro ao tentar encontrar o servidor. Tente novamente mais tarde.", ephemeral=True)
            return

        proibido_role = discord.utils.get(guild.roles, name="Proibido de Refazer Allowlist")
        if proibido_role and proibido_role in user.roles:
            await interaction.response.send_message("Você está bloqueado de realizar a allowlist novamente.", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(CATEGORY_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, read_message_history=True, send_messages=True)
        }
        channel = await guild.create_text_channel(f"Al-{user.name}", overwrites=overwrites, category=category)

        embed = discord.Embed(
            title="Instruções para Allowlist",
            description=f"Olá, {user.name}! Responda as perguntas abaixo com seriedade, pois elas serão avaliadas. Siga as etapas abaixo e qualquer dúvida, [abra um ticket](https://discord.com/channels/123).\n- A sua data de nascimento deve estar no formato dd/mm/aaaa.\n- O nome do seu personagem deve ser registrável em cartório.",
            color=discord.Color.dark_embed()
        )
        message = await channel.send(
            f"{user.mention}",
            embed=embed,
        )
        
        await message.pin()

        embed = discord.Embed(
            title="Fornecer dados necessários",
            description=f"{user.name}, antes de iniciar sua allowlist, precisamos de alguns dados pessoais. Clique no botão abaixo para adicionar os dados necessários e iniciar sua allowlist.",
            color=discord.Color.blue()
        )
        await channel.send(embed=embed, view=DataFormView(user, channel))

        embed = discord.Embed(
            title=f"**Allowlist**",
            description=f"Seu canal de Allowlist foi criado. Clique [aqui](https://discord.com/channels/{guild.id}/{channel.id}) para ir até ele.",
            color=discord.Color.green()
        )
        embed.set_author(name="",url=bot.user.avatar.url)
    
        await interaction.response.send_message(embed=embed, ephemeral=True)

class DataFormView(View):
    def __init__(self, user, channel):
        super().__init__(timeout=None)
        self.user = user
        self.channel = channel

    @discord.ui.button(label="Adicionar dados necessários", style=discord.ButtonStyle.primary)
    async def add_data(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.send_modal(DataModal(user=self.user, channel=self.channel))

### Verifica se o usuário tem mais de 18 anos
class DataModal(Modal, title="Adicionar Dados Necessários"):
    nome = TextInput(label="Nome completo", placeholder="Nome completo na vida real")
    personagem = TextInput(label="Nome e Sobrenome do Personagem", placeholder="Nome e Sobrenome do seu Personagem")
    data = TextInput(label="Sua data de nascimento", placeholder="xx/xx/xxxx")
    age = TextInput(label="Sua Idade", placeholder="Sua idade na vida real")

    def __init__(self, user: discord.User, channel: discord.TextChannel):
        super().__init__()
        self.user = user
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        nome = self.nome.value
        data = self.data.value
        personagem = self.personagem.value
        age = self.age.value

        if not age.isdigit() or len(age) != 2 or int(age) < 18:
            await interaction.response.send_message("Idade inválida ou abaixo do permitido.", ephemeral=True)
            await self.channel.delete(reason="Idade do usuário abaixo do permitido")
            return
        
        try:
            birth_date = datetime.strptime(data, '%d/%m/%Y')
            formatted_data = birth_date.strftime('%d/%m/%Y')
            today = datetime.today()
            age_calculated = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

            if age_calculated < 18:
                await interaction.response.send_message("Você deve ter 18 anos ou mais para se registrar.", ephemeral=True)
                await asyncio.sleep(15)
                await self.channel.delete(reason="Usuário com menos de 18 anos")
                return

        except ValueError:
            await interaction.response.send_message("Data de nascimento inválida. Certifique-se de que está no formato dd/mm/aaaa.", ephemeral=True)
            return

        user_responses[self.user.id] = {
            "data": formatted_data,
            "nome": nome,
            "personagem": personagem,
            "age": age,
            "correct": 0,
            "total": len(WhitelistManager.questions),
            "responses": [],
            "message": None,
        }

        await interaction.response.send_message("Dados armazenados com sucesso! Sua allowlist pode ser iniciada.", ephemeral=True)
        await interaction.message.delete()

        embed = discord.Embed(
            title="Iniciar Allowlist",
            description="Clique no botão abaixo para começar o teste de allowlist!",
            color=discord.Color.dark_embed()
        )
        view = StartWhitelistButtonView()
        await self.channel.send(embed=embed, view=view)

class StartWhitelistButtonView(View):
    @discord.ui.button(label="📑 Iniciar Allowlist", style=discord.ButtonStyle.primary)
    async def start_whitelist(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.message.delete()
        await WhitelistManager.send_next_question(interaction.channel, interaction.user)

class QuestionSelect(Select):
    def __init__(self, options, correct_answer, message_id):
        super().__init__(placeholder="Selecione uma opção", options=[
            discord.SelectOption(label=label, value=value) for label, value in options.items()
        ], min_values=1, max_values=1)
        self.correct_answer = correct_answer
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id not in user_responses:
            user_responses[user_id] = {"responses": [], "correct": 0}

        selected_value = self.values[0]

        if selected_value == self.correct_answer:
            user_responses[user_id]["correct"] += 1

        user_responses[user_id]["responses"].append(selected_value)

        if user_id in user_messages:
            previous_message_id = user_messages[user_id]
            channel = interaction.channel
            try:
                message = await channel.fetch_message(previous_message_id)
                await message.delete()
            except discord.NotFound:
                pass

        await WhitelistManager.send_next_question(interaction.channel, interaction.user)

class QuestionView(View):
    def __init__(self, answers, correct_answer, message_id):
        super().__init__(timeout=180.0)
        self.message_id = message_id
        self.add_item(QuestionSelect(answers, correct_answer, message_id))


### Perguntas da Allowlist
class WhitelistManager:
    questions = [
    {
        "question": "O que é Power Gaming em GTA RP?",
        "answers": {
            "Ignorar as regras do servidor para ganhar vantagem": "Ignorar as regras do servidor para ganhar vantagem",
            "Interpretar o personagem de forma realista e coerente": "Interpretar o personagem de forma realista e coerente",
            "Exagerar as habilidades do personagem para vencer em qualquer situação": "Exagerar as habilidades do personagem para vencer em qualquer situação",
            "Cooperar com outros jogadores para uma experiência mais divertida": "Cooperar com outros jogadores para uma experiência mais divertida"
        },
        "correct_answer": "Exagerar as habilidades do personagem para vencer em qualquer situação"
    },
    {
        "question": "O que significa 'Amor à Vida' em GTA RP?",
        "answers": {
            "A prioridade é proteger a vida do personagem e evitar mortes desnecessárias": "A prioridade é proteger a vida do personagem e evitar mortes desnecessárias",
            "O personagem deve buscar constantemente a morte para uma experiência mais realista": "O personagem deve buscar constantemente a morte para uma experiência mais realista",
            "O personagem deve viver uma vida luxuosa e desprezar a segurança": "O personagem deve viver uma vida luxuosa e desprezar a segurança",
            "A vida do personagem é secundária em relação a objetivos de jogo": "A vida do personagem é secundária em relação a objetivos de jogo"
        },
        "correct_answer": "A prioridade é proteger a vida do personagem e evitar mortes desnecessárias"
    },
    {
        "question": "O que é Metagaming em GTA RP?",
        "answers": {
            "Usar informações obtidas fora do jogo para tomar decisões no jogo": "Usar informações obtidas fora do jogo para tomar decisões no jogo",
            "Compartilhar informações do jogo com outros jogadores": "Compartilhar informações do jogo com outros jogadores",
            "Criar estratégias com base apenas no que o personagem sabe": "Criar estratégias com base apenas no que o personagem sabe",
            "Utilizar táticas e técnicas de jogo para melhorar o desempenho": "Utilizar táticas e técnicas de jogo para melhorar o desempenho"
        },
        "correct_answer": "Usar informações obtidas fora do jogo para tomar decisões no jogo"
    },
    {
        "question": "O que significa RDM (Random Deathmatch) em GTA RP?",
        "answers": {
            "Matar outros jogadores sem uma razão válida ou RP": "Matar outros jogadores sem uma razão válida ou RP",
            "Matar outros jogadores como parte de uma missão de RP": "Matar outros jogadores como parte de uma missão de RP",
            "Matar jogadores apenas se estiver em uma gangue rival": "Matar jogadores apenas se estiver em uma gangue rival",
            "Matar jogadores em resposta a provocações dentro do jogo": "Matar jogadores em resposta a provocações dentro do jogo"
        },
        "correct_answer": "Matar outros jogadores sem uma razão válida ou RP"
    },
    {
        "question": "O que é VDM (Vehicle Deathmatch) em GTA RP?",
        "answers": {
            "Usar veículos para matar jogadores sem uma razão válida ou RP": "Usar veículos para matar jogadores sem uma razão válida ou RP",
            "Utilizar veículos para transporte e atividades de RP": "Utilizar veículos para transporte e atividades de RP",
            "Matar jogadores apenas se eles estiverem em um veículo": "Matar jogadores apenas se eles estiverem em um veículo",
            "Atacar veículos de outros jogadores para roubar itens": "Atacar veículos de outros jogadores para roubar itens"
        },
        "correct_answer": "Usar veículos para matar jogadores sem uma razão válida ou RP"
    },
    {
        "question": 'Você foi indicado por algum jogador? Se sim, informe o ID/Passaporte dele. Se não foi indicado, informe que não.',
        "answers": {},
        "correct_answer": None
    }
    ]

    @staticmethod
    async def send_next_question(channel: discord.TextChannel, user: discord.User):
        user_id = user.id
        user_data = user_responses.setdefault(user_id, {"responses": [], "correct": 0, "total": len(WhitelistManager.questions) - 1})
        
        current_question_index = len(user_data["responses"])
        
        if current_question_index < len(WhitelistManager.questions) - 1:
            question_data = WhitelistManager.questions[current_question_index]
            embed = discord.Embed(title=None, description=question_data["question"], color=discord.Color.dark_embed())
            answers = question_data["answers"]
            view = QuestionView(answers, question_data["correct_answer"], user_messages.get(user_id))
            await channel.send(embed=embed, view=view)
            user_messages[user_id] = channel.last_message_id
        elif current_question_index == len(WhitelistManager.questions) - 1:
            question_data = WhitelistManager.questions[current_question_index]
            embed = discord.Embed(title=None, description=question_data["question"], color=discord.Color.dark_embed())
            message = await channel.send(embed=embed)
            user_messages[user_id] = channel.last_message_id
            def check(m):
                return m.author == user and m.channel == channel

            try:
                response_message = await bot.wait_for('message', timeout=60.0, check=check)
                user_data["responses"].append(response_message.content)
                
                await message.delete()

                await response_message.delete()
                await WhitelistManager.finalize_test(channel, user)#, formatar_data)
            except asyncio.TimeoutError:
                await channel.send("Tempo esgotado! Por favor, tente novamente.")
        else:
            await WhitelistManager.finalize_test(channel, user)#, formatar_data)

    @staticmethod
    async def finalize_test(channel: discord.TextChannel, user: discord.User):
        user_data = user_responses.get(user.id, {})
        correct_answers = user_data.get("correct", 0)
        total_questions = len(WhitelistManager.questions) - 1
        percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

        friend_referral = user_data.get("responses")[-1] if len(user_data.get("responses", [])) > len(WhitelistManager.questions) - 2 else "N/A"

        result_embed = discord.Embed(
            title="Allowlist"
        )
        result_embed.set_footer(text="🕐 Em 1 minuto esse canal será excluído automaticamente!")

        ### Config de porcentagem de acerto para ser aprovado, reprovado com opção de refazer e sem opção de refazer
        if percentage >= 80:
            role_id = ENTREVISTA_ROLE_ID
            result_embed.color = discord.Color.green()
            result_embed.description = f"Parabéns, **{user.name}**! Sua allowlist foi **Aprovada**! Para dar prosseguimento à sua liberação, precisamos fazer uma entrevista e, para isso, verifique os horários de entrevistas em https://discord.com/channels/840793938206261268/1267482606497431624 e fique de olho no canal https://discord.com/channels/840793938206261268/840793938948522075."
        elif 40 <= percentage < 80:
            role_id = REFAZER_ROLE_ID
            result_embed.color = discord.Color.orange()
            result_embed.description = f"**{user.name}**, infelizmente sua allowlist foi **Reprovada**, mas você pode refazer ela mais tarde. Para isso, estude mais sobre as regras do servidor e do Roleplay e boa sorte."
        else:
            role_id = REPROVADO_ROLE_ID
            result_embed.color = discord.Color.red()
            result_embed.description = f"**{user.name}**, infelizmente sua allowlist foi **Reprovada**. Agradecemos a sua tentativa."

        sem_wl_role = discord.utils.get(user.guild.roles, id=SEM_WL_ROLE_ID)
        if isinstance(sem_wl_role, discord.Role):
            await user.remove_roles(sem_wl_role)

        if role_id:
            role = discord.utils.get(user.guild.roles, id=role_id)
            if isinstance(role, discord.Role):
                await user.add_roles(role)
            else:
                result_embed.description += " "

        await channel.send(
            f"{user.mention}",
            embed=result_embed,
        )
        #await channel.send(embed=result_embed)

        log_channel = bot.get_channel(LOG_CHANNEL_ID_allowlist)
        if log_channel is not None:
            log_embed = discord.Embed(
                title=f"Allowlist do usuário {user.display_name}",
                description=(
                    f"`{user.id}`\n"
                    f"> **Nome completo:** `{user_data.get('nome', 'N/A')}`\n"
                    f"> **Data de Nascimento:** `{user_data.get('data', 'N/A')}`\n"
                    f"> **Nome e sobrenome do Personagem:** `{user_data.get('personagem', 'N/A')}`\n"
                    f"> **Idade:** {user_data.get('age', 'N/A')} anos\n\n"
                    #f"**Nome do personagem:** {user_data.get('name', 'N/A')}\n"
                    #f"**Rg(ID):** {user_data.get('id', 'N/A')}\n\n"
                    f"- **Indicado por um amigo:** {friend_referral}\n\n"
                    f"**Acertos:** {correct_answers}\n"
                    f"**Resultado:** {'Aprovado' if percentage >= 80 else 'Reprovado com opção de refazer' if percentage >= 40 else 'Reprovado (Sem opção de refazer)'}"
                ),
                color=discord.Color.dark_embed()
            )
            if user.avatar:
                log_embed.set_thumbnail(url=user.avatar.url)
            else:
                log_embed.set_thumbnail(url=DISCORD_IMAGE_URL)

            if user.avatar:
                log_embed.set_footer(text=f"Registrado por {user.display_name}", icon_url=user.avatar.url)
            else:
                log_embed.set_footer(text=f'Registrado por {user.display_name}', icon_url=DISCORD_IMAGE_URL)
        
            await log_channel.send(
            f"{user.mention}",
            embed=log_embed,
            )

        await asyncio.sleep(60)
        await channel.delete(reason="Allowlist concluída")

        user_responses.pop(user.id, None)
        user_messages.pop(user.id, None)

### Inicia o Bot e envia o embed no canal de inicio da Allowlist    
@bot.event
async def on_ready():
    print('O bot está ONLINE')
    print(bot.user.name)
    print(bot.user.id)
    print('------------')
    await bot.tree.sync()
    print(f'Comandos sincronizados.')

    channel = bot.get_channel(FORM_CHANNEL_ID)
    bot.display_name = "© bergamini7 © © Todos os direitos reservados"
    if channel:
        async for message in channel.history(limit=15):
            if message.author == bot.user:
                await message.delete()
        embed = discord.Embed(
            title="Allowlist", 
            description="Nosso servidor conta com uma Allowlist fechada. Se você responder as perguntas corretamente, você passará por uma entrevista e somente depois de aprovado na entrevista, poderá entrar no servidor.\n- Caso tenha algum problema ou dúvida, [abra um ticket](https://discord.com/channels/123).\n\n**Clique no botão abaixo para iniciar sua Allowlist!!**", 
            color=discord.Color.dark_embed()
        )
        if bot.user.avatar:
            embed.set_footer(text=f"{bot.display_name}", icon_url=bot.user.avatar.url)
        else:
            embed.set_footer(text=f"{bot.display_name}")
        embed.set_thumbnail(url=PANEL_IMAGE_URL)
        view = View()
        view.add_item(StartWhitelistButton())

        await channel.send(embed=embed, view=view)

### Token do bot
bot.run('TOKEN')